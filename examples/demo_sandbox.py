import asyncio
from orkestra.core.tools import Tool
import time
import requests

def test_network_exfiltration():
    # Attempt to fetch from external site
    try:
        import urllib.request
        req = urllib.request.urlopen('http://google.com', timeout=3)
        return req.read().decode('utf-8')[:50]
    except Exception as e:
        return f"Network blocked: {str(e)}"

def test_memory_bomb():
    # Attempt to allocate huge amounts of memory
    print("Allocating memory...")
    a = []
    try:
        while True:
            a.append("A" * 10**7)
    except MemoryError:
        return "MemoryError caught (if allowed)"
    except Exception as e:
        return str(e)
    return "Surviving"

def test_timeout():
    import time
    # Attempt to hang the tool
    time.sleep(100)
    return "Should not reach here"

async def run_demo():
    print("=== Orkestra Sandbox Hardening Demo ===")
    
    # 1. Network Test
    net_tool = Tool(
        name="test_network",
        description="Try to access internet",
        func=test_network_exfiltration,
        schema={},
        network_access=False
    )
    print("\n[TEST] Testing Network Exfiltration (network_access=False)")
    result = await net_tool.arun()
    print(f"Result: {result}")
    
    # 2. Memory Limit Test
    mem_tool = Tool(
        name="test_memory",
        description="Try to exhaust memory",
        func=test_memory_bomb,
        schema={}
    )
    print("\n[TEST] Testing Memory Bomb (512m limit)")
    result = await mem_tool.arun()
    print(f"Result: {result}")
    
    # 3. Timeout Test
    time_tool = Tool(
        name="test_timeout",
        description="Try to hang forever",
        func=test_timeout,
        schema={},
        timeout_seconds=3
    )
    print("\n[TEST] Testing Execution Timeout (3s limit)")
    result = await time_tool.arun()
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(run_demo())
