import sys
import re

file_path = r"c:\Users\LENOVO\Desktop\Anuman.ai\docs\index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

func_str = """
function autoDetectLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                const data = await res.json();
                const city = data.address.city || data.address.town || data.address.village || data.address.county;

                if(city) {
                    const locationInput = document.getElementById('location-search');
                    if (locationInput) locationInput.value = city;
                }
            } catch(e) { console.log("Location auto-detect failed", e); }
        }, (error) => {
            console.log("User denied location permission");
        });
    }
}
"""
content = content.replace("<script>", "<script>\n" + func_str, 1)

content = re.sub(
    r"(document\.addEventListener\('DOMContentLoaded',\s*(?:async\s*)?(?:function\s*\([^\)]*\)\s*|\([^\)]*\)\s*=>)\s*\{)",
    r"\1\n    autoDetectLocation();\n",
    content
)

pattern = r"(try\s*\{\s*)(const\s+res\s*=\s*await\s+fetch\([^,]+,\s*\{\s*method:\s*'POST',\s*headers:\s*\{\s*'Content-Type':\s*'application/json'\s*\},\s*body:\s*JSON\.stringify\(\{\s*message:\s*query,\s*session_id:\s*currentUserSessionId,\s*is_voice:\s*isVoiceQuery[^\}]*\}\)\s*\}\);)"

new_inner = r"""const currentLocation = document.getElementById('location-search') ? document.getElementById('location-search').value : '';
            const smartQuery = currentLocation ? `${query} (Context: User is currently in ${currentLocation})` : query;

            const res = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: smartQuery, 
                    session_id: currentUserSessionId,
                    is_voice: isVoiceQuery 
                }) 
            });"""

def replacer(match):
    return match.group(1) + new_inner

content = re.sub(pattern, replacer, content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Replacement done.")
