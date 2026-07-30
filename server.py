# ==============================================================================
# ENTERPRISE PYTHON-TO-C++ HARDWARE TRANSPILER ENGINE
# Translates Python Hardware Code into Arduino/ESP C++ (Arduino Framework)
# ==============================================================================
import os
import re
import ast
from flask import Flask, request, jsonify

app = Flask(__name__)

def convert_python_to_cpp(raw_code: str) -> str:
    """
    Sanitizes raw Python/mixed input and converts it into valid ESP/Arduino C++ code.
    """
    if not raw_code or not raw_code.strip():
        return (
            "#include <Arduino.h>\n\n"
            "void setup() {}\n"
            "void loop() {}\n"
        )

    # 1. Clean and normalize input lines
    lines = raw_code.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        
        # Remove Python comments or C++ style comments
        if stripped.startswith("#") and not stripped.startswith("#include"):
            continue
        if "//" in stripped:
            stripped = stripped.split("//")[0].strip()

        # Fix broken delay/sleep typos: time.sleep(.) -> time.sleep(1.0)
        stripped = re.sub(r'time\.sleep\(\s*\.\s*\)', 'time.sleep(1.0)', stripped)
        stripped = re.sub(r'delay\(\s*\.\s*\)', 'delay(1000)', stripped)

        if stripped:
            cleaned_lines.append(stripped)

    clean_text = "\n".join(cleaned_lines)

    # 2. Safely extract Pin Numbers
    explicit_pins = re.findall(r'(?:pin_|Pin\(|digitalWrite\(\s*|pin\s*=\s*)(\d+)', clean_text, re.IGNORECASE)
    
    unique_pins = []
    for p in explicit_pins:
        if p not in unique_pins and int(p) <= 40:
            unique_pins.append(p)

    if not unique_pins:
        unique_pins = ["5", "0", "14", "13", "2", "1"]

    # 3. Build Loop Body (Translating Python lines into C++)
    loop_body = []

    for line in cleaned_lines:
        line_lower = line.lower()

        # Handle Sleep / Delay conversion
        if "sleep" in line_lower or "delay" in line_lower:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            if nums:
                val = float(nums[0])
                # If value is in seconds (< 100), convert to milliseconds for C++ delay()
                ms = int(val * 1000) if val <= 100 else int(val)
                ms = max(100, ms)
            else:
                ms = 1000
            loop_body.append(f"  delay({ms});")

        # Handle Setting Pins HIGH / ON
        elif "high" in line_lower or "value(1)" in line_lower or ("digitalwrite" in line_lower and ("1" in line_lower or "true" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                loop_body.append(f"  digitalWrite({pin}, HIGH);")

        # Handle Setting Pins LOW / OFF
        elif "low" in line_lower or "value(0)" in line_lower or ("digitalwrite" in line_lower and ("0" in line_lower or "false" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                loop_body.append(f"  digitalWrite({pin}, LOW);")

    # Fallback pattern if no actionable pin triggers were identified
    if not loop_body:
        for pin in unique_pins:
            loop_body.append(f"  digitalWrite({pin}, HIGH);")
        loop_body.append("  delay(1000);")
        for pin in unique_pins:
            loop_body.append(f"  digitalWrite({pin}, LOW);")
        loop_body.append("  delay(500);")

    # 4. Construct Complete C++ File Output
    cpp_output = [
        "#include <Arduino.h>",
        "",
        "// Pin Definitions",
    ]
    for pin in unique_pins:
        cpp_output.append(f"const int PIN_{pin} = {pin};")

    cpp_output.extend([
        "",
        "void setup() {"
    ])

    for pin in unique_pins:
        cpp_output.append(f"  pinMode({pin}, OUTPUT);")

    cpp_output.extend([
        "}",
        "",
        "void loop() {"
    ])
    
    cpp_output.extend(loop_body)
    cpp_output.extend([
        "}",
        ""
    ])

    return "\n".join(cpp_output)


# ------------------------------------------------------------------------------
# REST API ENDPOINTS
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """Web Dashboard for Testing Python to C++ Conversion"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Python to C++ Hardware Transpiler</title>
        <style>
            body { font-family: system-ui, sans-serif; padding: 25px; background: #090d16; color: #f8fafc; }
            textarea { width: 100%; height: 260px; background: #1e293b; color: #38bdf8; font-family: monospace; padding: 14px; border-radius: 8px; border: 1px solid #334155; }
            button { background: #0284c7; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 12px; font-weight: bold; }
            button:hover { background: #0369a1; }
            pre { background: #1e293b; padding: 18px; color: #4ade80; border-radius: 8px; font-family: monospace; border: 1px solid #334155; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h2>Python to ESP/Arduino C++ Transpiler</h2>
        <p>Paste your Python code below to generate valid C++ (.ino) code:</p>
        <textarea id="code">from machine import Pin\nimport time\n\npin_5 = Pin(5, Pin.OUT)\npin_5.value(1)\ntime.sleep(1.0)\npin_5.value(0)\ntime.sleep(.)</textarea><br>
        <button onclick="transpile()">Transpile to C++</button>
        <h3>Generated ESP/Arduino C++ Output:</h3>
        <pre id="output">C++ output will render here...</pre>

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
    """REST API Endpoint for Clients"""
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "")
    cpp_result = convert_python_to_cpp(raw_code)
    return jsonify({
        "status": "success",
        "result": cpp_result
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("==================================================")
    print("  PYTHON TO C++ TRANSPILER SERVER RUNNING         ")
    print(f"  URL: http://0.0.0.0:{port}                     ")
    print("==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
        
