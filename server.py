import os
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

def sanitize_and_transpile(raw_code: str) -> str:
    """
    Cleans raw Python/mixed input, strips unwanted imports,
    and returns valid, crash-proof MicroPython code for ESP boards.
    """
    if not raw_code or not raw_code.strip():
        return "from machine import Pin\nimport time\n"

    lines = raw_code.splitlines()
    cleaned_lines = []
    in_cpp_block = False

    for line in lines:
        stripped = line.strip()

        # Handle unwanted or desktop imports
        if stripped.startswith("import ") or stripped.startswith("from "):
            if any(mod in stripped for mod in ["machine", "time", "utime", "urequests", "ujson"]):
                cleaned_lines.append(stripped)
            continue

        # Strip C++ blocks
        if stripped.startswith("#include") or "void setup" in stripped or "void loop" in stripped:
            in_cpp_block = True
            continue
        if stripped == "}" and in_cpp_block:
            in_cpp_block = False
            continue
        if in_cpp_block:
            continue

        # Remove C++ style inline comments
        if "//" in stripped:
            stripped = stripped.split("//")[0].strip()

        # Fix malformed delay dots: time.sleep(.) -> time.sleep(1.0)
        stripped = re.sub(r'time\.sleep\(\s*\.\s*\)', 'time.sleep(1.0)', stripped)

        if stripped:
            cleaned_lines.append(stripped)

    clean_text = "\n".join(cleaned_lines)

    # Detect GPIO Pin Numbers (e.g. 5, 0, 14, 13, 2, 1)
    explicit_pins = re.findall(r'(?:pin_|Pin\(|digitalWrite\(\s*)(\d+)', clean_text, re.IGNORECASE)
    unique_pins = []
    for p in explicit_pins:
        if p not in unique_pins and int(p) <= 40:
            unique_pins.append(p)

    if not unique_pins:
        unique_pins = ["5", "0", "14", "13", "2", "1"]

    # Header construction
    output_lines = [
        "from machine import Pin",
        "import time",
        ""
    ]
    
    for pin in unique_pins:
        output_lines.append(f"pin_{pin} = Pin({pin}, Pin.OUT)")
    output_lines.append("")

    # Parse logic lines
    for line in cleaned_lines:
        line_lower = line.lower()

        # Delays
        if "sleep" in line_lower or "delay" in line_lower or "wait" in line_lower:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            if nums:
                val = float(nums[0])
                secs = val / 1000.0 if val > 100 else val
                secs = max(0.1, secs)
            else:
                secs = 1.0
            output_lines.append(f"time.sleep({secs:.1f})")

        # Turn Pins ON
        elif "high" in line_lower or "value(1)" in line_lower or "glow" in line_lower or ("digitalwrite" in line_lower and ("1" in line_lower or "true" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                output_lines.append(f"pin_{pin}.value(1)")

        # Turn Pins OFF
        elif "low" in line_lower or "value(0)" in line_lower or "off" in line_lower or ("digitalwrite" in line_lower and ("0" in line_lower or "false" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                output_lines.append(f"pin_{pin}.value(0)")

    return "\n".join(output_lines)


@app.route("/", methods=["GET"])
def home():
    """Dark Styled Web Dashboard"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Offline MicroPython Transpiler Server</title>
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; padding: 25px; background: #0f172a; color: #f8fafc; margin: 0; }
            .container { max-width: 900px; margin: 0 auto; }
            h2 { color: #38bdf8; font-weight: 700; margin-bottom: 8px; }
            p { color: #94a3b8; margin-top: 0; }
            textarea { width: 100%; height: 220px; background: #1e293b; color: #38bdf8; font-family: monospace; padding: 14px; border-radius: 8px; border: 1px solid #334155; font-size: 14px; box-sizing: border-box; }
            button { background: #0284c7; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: bold; margin-top: 12px; transition: background 0.2s; }
            button:hover { background: #0369a1; }
            pre { background: #1e293b; padding: 18px; color: #4ade80; border-radius: 8px; font-family: monospace; border: 1px solid #334155; overflow-x: auto; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Offline Hardware Code Sanitizer & Transpiler</h2>
            <p>Paste any Python, MicroPython, or pseudo-code below to generate ESP payload:</p>
            <textarea id="code">digitalWrite(5, HIGH)\ntime.sleep(1.0)\ndigitalWrite(5, LOW)\ntime.sleep(0.5)</textarea><br>
            <button onclick="transpile()">Transpile Code</button>
            <h3>Clean MicroPython Output (Sent to ESP8266):</h3>
            <pre id="output">Output will appear here...</pre>
        </div>

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
    """Endpoint for ESP8266 and Web Clients"""
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "") or data.get("raw_code", "")

    if not raw_code and request.data:
        raw_code = request.data.decode("utf-8", errors="ignore")

    result_code = sanitize_and_transpile(raw_code)
    return jsonify({
        "status": "success",
        "result": result_code
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
    
