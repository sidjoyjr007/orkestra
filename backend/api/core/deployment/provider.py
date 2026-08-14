import abc
import subprocess
import uuid
import socket
import logging
import os

logger = logging.getLogger(__name__)

class BaseDeploymentProvider(abc.ABC):
    @abc.abstractmethod
    async def deploy(self, agent_id: str, control_plane_url: str, deployment_token: str) -> dict:
        """Deploys an agent and returns metadata like container_id and port"""
        pass

    @abc.abstractmethod
    async def deploy_swarm(self, swarm_id: str, control_plane_url: str, deployment_token: str) -> dict:
        """Deploys a swarm and returns metadata like container_id and port"""
        pass

    @abc.abstractmethod
    async def stop(self, container_id: str):
        pass

    @abc.abstractmethod
    async def start(self, container_id: str):
        pass

    @abc.abstractmethod
    async def remove(self, container_id: str):
        pass

    @abc.abstractmethod
    async def get_status(self, container_id: str) -> str:
        pass

class LocalDockerProvider(BaseDeploymentProvider):
    def __init__(self):
        self.image_name = "orkestra-runner:latest"
        
    def _find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    async def _run_container(self, cmd_prefix, container_name, port, control_plane_url, extra_env=None, override_cmd=None):
        cmd = cmd_prefix + [
            "--name", container_name,
            "-p", f"{port}:8000",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-e", f"CONTROL_PLANE_URL={control_plane_url}"
        ]
        
        if extra_env:
            for k, v in extra_env.items():
                cmd.extend(["-e", f"{k}={v}"])
                
        # Forward API Keys from Host to Container
        api_keys = ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TAVILY_API_KEY"]
        for key in api_keys:
            val = os.environ.get(key)
            if val:
                cmd.extend(["-e", f"{key}={val}"])
                
        # Forward Vector DB and Workspace DB URLs
        tool_reg = os.environ.get("TOOL_REGISTRY_URL", control_plane_url.replace(":8000", ":8100"))
        cmd.extend(["-e", f"TOOL_REGISTRY_URL={tool_reg}"])
        
        from backend.api.core.config import settings
        
        workspace_db = os.environ.get("WORKSPACE_DB_URL")
        if not workspace_db:
            workspace_db = settings.AUTH_DATABASE_URL.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
            
        cmd.extend(["-e", f"WORKSPACE_DB_URL={workspace_db}"])
        cmd.extend(["-e", f"MEMORY_DATABASE_URL={workspace_db}"]) # Use the same state database for memory
                
        cmd.append(self.image_name)
        
        if override_cmd:
            cmd.extend(override_cmd)
        
        try:
            # We run synchronously for local deployment, but this should be non-blocking in prod
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_id = result.stdout.strip()
            return {
                "container_id": container_id,
                "port": port
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to deploy docker container: {e.stderr}")
            raise Exception(f"Docker deployment failed: {e.stderr}")

    async def deploy(self, agent_id: str, control_plane_url: str, deployment_token: str) -> dict:
        port = self._find_free_port()
        container_name = f"orkestra-agent-{agent_id}-{uuid.uuid4().hex[:6]}"
        extra_env = {
            "AGENT_ID": agent_id,
            "DEPLOYMENT_TOKEN": deployment_token
        }
        return await self._run_container(["docker", "run", "-d"], container_name, port, control_plane_url, extra_env)

    async def deploy_swarm(self, swarm_id: str, control_plane_url: str, deployment_token: str) -> dict:
        port = self._find_free_port()
        container_name = f"orkestra-swarm-{swarm_id}-{uuid.uuid4().hex[:6]}"
        
        extra_env = {
            "SWARM_ID": swarm_id,
            "DEPLOYMENT_TOKEN": deployment_token
        }
        
        # We need to mount our new swarm_runner.py and the latest orkestra code
        swarm_runner_path = "/Users/siddeshhn/Desktop/orkestra/deployments/runner/swarm_runner.py"
        src_path = "/Users/siddeshhn/Desktop/orkestra/src/orkestra"
        cmd_prefix = [
            "docker", "run", "-d",
            "-v", f"{swarm_runner_path}:/app/swarm_runner.py",
            "-v", f"{src_path}:/app/orkestra"
        ]
        
        return await self._run_container(
            cmd_prefix, 
            container_name, 
            port, 
            control_plane_url, 
            extra_env, 
            override_cmd=["python", "swarm_runner.py"]
        )

    async def stop(self, container_id: str):
        try:
            subprocess.run(["docker", "stop", container_id], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop container {container_id}: {e}")

    async def start(self, container_id: str):
        try:
            subprocess.run(["docker", "start", container_id], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            raise Exception(f"Docker start failed: {e.stderr}")

    async def remove(self, container_id: str):
        try:
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove container {container_id}: {e}")

    async def get_status(self, container_id: str) -> str:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_id],
                capture_output=True, text=True, check=True
            )
            status = result.stdout.strip().lower()
            if status == "running":
                return "RUNNING"
            elif status == "paused":
                return "PAUSED"
            elif status in ["exited", "stopped", "created"]:
                return "STOPPED"
            return "UNKNOWN"
        except subprocess.CalledProcessError:
            # Container might not exist or has been removed
            return "STOPPED"
