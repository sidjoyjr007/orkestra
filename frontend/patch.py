import os
import re

files_to_patch = [
    "src/pages/ChangePassword.jsx",
    "src/App.jsx",
    "src/pages/ToolsHub.jsx",
    "src/pages/Login.jsx",
    "src/pages/AdminApprovals.jsx",
    "src/pages/CreateTool.jsx"
]

for filepath in files_to_patch:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Inject import after the last import statement
    if 'import { API_BASE_URL } from "@/config"' not in content:
        import_matches = list(re.finditer(r'^import .*$', content, re.MULTILINE))
        if import_matches:
            last_import = import_matches[-1]
            insert_pos = last_import.end()
            content = content[:insert_pos] + '\nimport { API_BASE_URL } from "@/config"' + content[insert_pos:]
    
    # Replace the URLs
    content = content.replace('"http://localhost:8000/api', '`${API_BASE_URL}/api')
    content = content.replace('http://localhost:8000/api', '${API_BASE_URL}/api')
    
    # Handle the weird `http://localhost:8000${endpoint}`
    content = content.replace('`http://localhost:8000${endpoint}`', '`${API_BASE_URL}${endpoint}`')
    
    # Also if there are trailing quotes missing because of replace
    content = re.sub(r'`\$\{API_BASE_URL\}([^`"\']+)["\']', r'`${API_BASE_URL}\1`', content)

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Patched {filepath}")

