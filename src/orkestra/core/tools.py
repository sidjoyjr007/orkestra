import inspect
import json
import os
import sys
import tempfile
import subprocess
import asyncio
from typing import Any, Callable, Dict, List, Optional
import hashlib
from orkestra.core.exceptions import WorkflowPausedError

class Tool:
    """
    A tool that runs its function in an isolated Docker container with dynamic dependencies.
    Provides strict security sandboxing (no host file system access).
    """
    def __init__(self, name: str, description: str, func: Callable, schema: Dict[str, Any], dependencies: List[str] = None, timeout_seconds: int = 60, requires_approval: bool = False, max_result_length: int = 24000, network_access: bool = False):
        self.name = name
        self.description = description
        self.func = func
        self.schema = schema
        self.dependencies = dependencies or []
        self.timeout_seconds = timeout_seconds
        self.requires_approval = requires_approval
        self.max_result_length = max_result_length
        self.network_access = network_access
        
        # Hash dependencies to create a unique cache tag
        deps_str = "-".join(sorted(self.dependencies)) if self.dependencies else "none"
        hash_digest = hashlib.sha256(deps_str.encode()).hexdigest()[:12]
        self.image_tag = f"orkestra-tool:{hash_digest}"
        
    def _ensure_image(self):
        """Builds the Docker image if it doesn't already exist."""
        # Check if image exists in Docker cache
        check = subprocess.run(["docker", "image", "inspect", self.image_tag], capture_output=True)
        if check.returncode == 0:
            return  # Cache hit!
            
        # Cache miss: Build the image
        with tempfile.TemporaryDirectory() as temp_dir:
            dockerfile_content = "FROM python:3.11-slim\nWORKDIR /app\n"
            if self.dependencies:
                # Filter out standard library modules
                import sys
                valid_deps = []
                for d in self.dependencies:
                    base_pkg = d.split('==')[0].split('[')[0].split('.')[0]
                    if base_pkg not in sys.stdlib_module_names:
                        valid_deps.append(d)
                
                if valid_deps:
                    deps = " ".join(valid_deps)
                    dockerfile_content += f"RUN pip install --no-cache-dir {deps}\n"
                
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
                
            subprocess.run(["docker", "build", "-t", self.image_tag, temp_dir], check=True, capture_output=True)

    def _execute_in_docker(self, kwargs: Dict[str, Any]) -> str:
        import textwrap
        try:
            if hasattr(self.func, '__source_code__'):
                func_source = self.func.__source_code__
            else:
                func_source = textwrap.dedent(inspect.getsource(self.func))
        except Exception as e:
            return json.dumps({"error": f"Could not extract source code for {self.name}: {str(e)}"})
            
        try:
            self._ensure_image()
        except subprocess.CalledProcessError as e:
            err_msg = f"Failed to build Docker sandbox for {self.name}: {e.stderr.decode()}"
            print(f"Sandbox Build Error: {err_msg}", file=sys.stderr)
            return json.dumps({"error": err_msg})

        # Strip internal Orkestra kwargs before passing to the user's function
        clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        # Double dump to safely inject JSON string literal into the python script
        safe_kwargs = json.dumps(json.dumps(clean_kwargs))
        func_name = self.func.__name__
        
        script = f"""
import json
import sys

# --- Tool Function ---
{func_source}
# ---------------------

if __name__ == '__main__':
    try:
        kwargs = json.loads({safe_kwargs})
        
        # Determine if function is async
        import inspect
        import asyncio
        if inspect.iscoroutinefunction({func_name}):
            result = asyncio.run({func_name}(**kwargs))
        else:
            result = {func_name}(**kwargs)
            
        print(json.dumps({{"status": "success", "result": result}}))
    except Exception as e:
        print(json.dumps({{"status": "error", "error": str(e)}}))
"""

        try:
            # Generate a unique workspace volume name based on the current deployment token
            deployment_token = os.environ.get("DEPLOYMENT_TOKEN", "default_local_run")
            volume_name = f"orkestra_workspace_{deployment_token}"
            
            # Ensure the volume exists
            subprocess.run(["docker", "volume", "create", volume_name], capture_output=True)

            # Construct the hardened docker command
            cmd = [
                "docker", "run", "-i", "--rm",
                "-v", f"{volume_name}:/sandbox",
                "-w", "/sandbox"
            ]
            
            # Resource Limits & Security
            cmd.extend([
                "--memory=512m", 
                "--cpus=0.5", 
                "--cap-drop=ALL"
            ])
            
            # Network Isolation Opt-in
            if not self.network_access:
                cmd.append("--network=none")
                
            cmd.extend([self.image_tag, "python", "-"])

            # Run the python script dynamically via stdin in a strict container
            process = subprocess.run(
                cmd,
                input=script,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"Tool execution timed out after {self.timeout_seconds} seconds."})
            
        if process.returncode != 0:
            err_msg = f"Tool execution failed: {process.stderr}"
            print(f"Sandbox Run Error: {err_msg}", file=sys.stderr)
            with open("/tmp/sandbox_errors.log", "a") as f: f.write(err_msg + "\\n")
            return json.dumps({"error": err_msg})
            
        try:
            output = json.loads(process.stdout)
            if output.get("status") == "error":
                return json.dumps({"error": output.get("error")})
            
            result = output.get("result")
            return result if isinstance(result, str) else json.dumps(result)
        except json.JSONDecodeError:
            err_msg = "Failed to parse tool output"
            print(f"Sandbox Parse Error: {err_msg}. Stdout: {process.stdout}", file=sys.stderr)
            with open("/tmp/sandbox_errors.log", "a") as f: f.write(err_msg + f" Stdout: {process.stdout}\\n")
            return json.dumps({"error": err_msg, "stdout": process.stdout})

    def run(self, **kwargs) -> str:
        return self._execute_in_docker(kwargs)
        
    async def arun(self, **kwargs) -> str:
        # Run the synchronous docker execution in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(self._execute_in_docker, kwargs)

class HostTool(Tool):
    """
    A tool that executes natively on the host machine instead of inside a Docker Sandbox.
    Use this for local IDE agents or internal servers where you want the agent to have direct filesystem access.
    """
    async def arun(self, **kwargs) -> str:
        # Strip internal Orkestra kwargs before passing to the user's function
        clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        try:
            if asyncio.iscoroutinefunction(self.func):
                return await self.func(**clean_kwargs)
            else:
                return self.func(**clean_kwargs)
        except WorkflowPausedError:
            raise
        except Exception as e:
            if type(e).__name__ == "HandoffException":
                raise
            return f"Error executing native tool '{self.name}': {str(e)}"
