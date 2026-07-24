import inspect
import json
import os
import tempfile
import subprocess
import asyncio
from typing import Any, Callable, Dict, List
import hashlib

class Tool:
    """
    A tool that runs its function in an isolated Docker container with dynamic dependencies.
    Provides strict security sandboxing (no host file system access).
    """
    def __init__(self, name: str, description: str, func: Callable, schema: Dict[str, Any], dependencies: List[str] = None, timeout_seconds: int = 60, requires_approval: bool = False, max_result_length: int = None, network_access: bool = False):
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
                deps = " ".join(self.dependencies)
                dockerfile_content += f"RUN pip install --no-cache-dir {deps}\n"
                
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
                
            subprocess.run(["docker", "build", "-t", self.image_tag, temp_dir], check=True, capture_output=True)

    def _execute_in_docker(self, kwargs: Dict[str, Any]) -> str:
        import textwrap
        try:
            func_source = textwrap.dedent(inspect.getsource(self.func))
        except Exception as e:
            return json.dumps({"error": f"Could not extract source code for {self.name}: {str(e)}"})
            
        try:
            self._ensure_image()
        except subprocess.CalledProcessError as e:
            return json.dumps({"error": f"Failed to build Docker sandbox for {self.name}: {e.stderr.decode()}"})

        # Double dump to safely inject JSON string literal into the python script
        safe_kwargs = json.dumps(json.dumps(kwargs))
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
            # Construct the hardened docker command
            cmd = ["docker", "run", "-i", "--rm"]
            
            # Resource Limits & Security
            cmd.extend([
                "--memory=512m", 
                "--cpus=0.5", 
                "--user=1000:1000", 
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
            return json.dumps({"error": f"Tool execution failed: {process.stderr}"})
            
        try:
            output = json.loads(process.stdout)
            if output.get("status") == "error":
                return json.dumps({"error": output.get("error")})
            
            result = output.get("result")
            return result if isinstance(result, str) else json.dumps(result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse tool output", "stdout": process.stdout})

    def run(self, **kwargs) -> str:
        return self._execute_in_docker(kwargs)
        
    async def arun(self, **kwargs) -> str:
        # Run the synchronous docker execution in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_in_docker, kwargs)
