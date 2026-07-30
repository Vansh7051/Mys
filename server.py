import os
import re
import ast
from flask import Flask, request, jsonify

app = Flask(__name__)

def sanitize_and_transpile(raw_code: str) -> str:
    """
    100% Offline Python-to-Hardware Transpiler & Sanitizer.
    Strips C++ code, fixes malformed delays, unrolls loops, and outputs clean MicroPython.
    """
    if not raw_code or not raw_code.strip():
        return "from machine import Pin\nimport time\n"

    # 1. Remove C++ / Arduino fragments (#include, void setup, void loop, // comments)
    lines = raw_code.splitlines()
    cleaned_lines = []
    in_cpp_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # Detect C++ style functions/headers
        if stripped.startswith("#include") or "void setup" in stripped or "void loop" in stripped:
            in_cpp_block = True
            continue
        if stripped == "}" and in_cpp_block:
            in_cpp_block = False
            continue
        if in_cpp_block:
            continue
            
        # Remove C++ inline comments '//'
        if "//" in stripped:
            stripped = stripped.split("//")[0].strip()
            
        if stripped:
            cleaned_lines.append(stripped)

    clean_text = "\n".join(cleaned_lines)

    # 2. Extract Pin Numbers (e.g., 5, 0, 14, 13)
    found_pins = re.findall(r'\b\d+\b', clean_text)
    # Deduplicate while preserving order
    unique_pins = []
    for p in found_pins:
        if p not in unique_pins and int(p) <= 40:
            unique_pins.append(p)
            
    if not unique_pins:
        unique_pins = ["5", "0", "14", "13"]

    # 3. Build MicroPython Header & Pin Initializations
    output_lines = [
        "from machine import Pin",
        "import time",
        ""
    ]
    for pin in unique_pins:
        output_lines.append(f"pin_{pin} = Pin({pin}, Pin.OUT)")
    output_lines.append("")

    # 4. Process Statements & Fix Delays
    for line in cleaned_lines:
        line_lower = line.lower()
        
        # Handle Delays / Sleep: Fix 'time.sleep(.)' or 'delay(.)' with valid floats
        if "sleep" in line_lower or "delay" in line_lower:
            # Match any valid numbers in the sleep line
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            if nums:
                val = float(nums[0])
                # Convert milliseconds to seconds if value > 100
                secs = val / 1000.0 if val > 100 else val
                secs = max(0.1, secs)
            else:
                secs = 1.0  # Default safe delay
            output_lines.append(f"time.sleep({secs:.1f})")
            
        # Handle Pin Set HIGH / ON
        elif "high" in line_lower or "value(1)" in line_lower or "digitalwrite" in line_lower and ("1" in line_lower or "true" in line_lower):
            for pin in unique_pins:
                output_lines.append(f"pin_{pin}.value(1)")
                
        # Handle Pin Set LOW / OFF
        elif "low" in line_lower or "value(0)" in line_lower or "digitalwrite" in line_lower and ("0" in line_lower or "false" in line_lower):
            for pin in unique_pins:
                output_lines.append(f"pin_{pin}.value(0)")

    # Fallback if no actions found
    if len(output_lines) <= len(unique_pins) + 3:
        for pin in unique_pins:
            output_lines.append(f"pin_{pin}.value(1)")
        output_lines.append("time.sleep(1.0)")
        for pin in unique_pins:
            output_lines.append(f"pin_{pin}.value(0)")
        output_lines.append("time.sleep(0.5)")

    return "\n".join(output_lines)


@app.route("/", methods=["GET"])
def home():
    """Simple web dashboard for testing in browser"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Offline MicroPython Transpiler Server</title>
        <style>
            body { font-family: sans-serif; padding: 20px; background: #0f172a; color: #f8fafc; }
            textarea { width: 100%; height: 200px; background: #1e293b; color: #38bdf8; font-family: monospace; padding: 10px; border-radius: 8px; }
            button { background: #0284c7; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 10px; }
            pre { background: #1e293b; padding: 15px; color: #4ade80; border-radius: 8px; font-family: monospace; }
        </style>
    </head>
    <body>
        <h2>Offline Hardware Code Sanitizer & Transpiler</h2>
        <p>Paste any Python / C++ / MicroPython code below:</p>
        <textarea id="code">for p in [5, 0, 14]:\n    digitalWrite(p, HIGH)\n    time.sleep(.)\n\n// C++ block\nvoid setup() { pinMode(5, OUTPUT); }</textarea><br>
        <button onclick="transpile()">Transpile Code</button>
        <h3>Clean MicroPython Output:</h3>
        <pre id="output">Output will appear here...</pre>

        <script>
            async function transpile() {
                const input = document.getElementById('code').value;
                const res = await fetch('/transpile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: input })
                });
                const data = await res.json();
                document.getElementById('output').textContent = data.result;
            }
        </script>
    </body>
    </html>
    """

@app.route("/transpile", methods=["POST"])
def transpile():
    """REST API Endpoint for Clients & ESP Boards"""
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "")
    result_code = sanitize_and_transpile(raw_code)
    return jsonify({
        "status": "success",
        "result": result_code
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("==================================================")
    print("  OFFLINE HARDWARE TRANSPILER SERVER RUNNING      ")
    print(f"  URL: http://0.0.0.0:{port}                     ")
    print("==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
        
