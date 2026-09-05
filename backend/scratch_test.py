import sys
import re

file_path = r"c:\Users\LENOVO\Desktop\Anuman.ai\docs\index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

print("Script found:", content.find("<script>"))

dom_match = re.search(r"(document\.addEventListener\('DOMContentLoaded',\s*(?:async\s*)?(?:function\s*\([^\)]*\)\s*|\([^\)]*\)\s*=>)\s*\{)", content)
print("DOM match:", bool(dom_match))

fetch_match = re.search(r"(try\s*\{\s*)(const\s+res\s*=\s*await\s+fetch\([^,]+,\s*\{\s*method:\s*'POST',\s*headers:\s*\{\s*'Content-Type':\s*'application/json'\s*\},\s*body:\s*JSON\.stringify\(\{\s*message:\s*query,\s*session_id:\s*currentUserSessionId,\s*is_voice:\s*isVoiceQuery[^\}]*\}\)\s*\}\);)", content)
print("Fetch match:", bool(fetch_match))

