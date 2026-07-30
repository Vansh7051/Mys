import os
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

def convert_to_cpp(cleaned_lines, unique_pins):
    """Generates C++ view for web display"""
    cpp_lines = [
        "#include <Arduino.h>",
        "",
        "void setup() {"
    ]
    for pin in unique_pins:
        cpp_lines.append(f"  pinMode({pin}, OUTPUT);")
    cpp_lines.extend(["}", "", "void loop() {"])

    for line in cleaned_lines:
        line_lower = line.lower()
        if "sleep" in line_lower or "delay" in line_lower:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            ms = int(float(nums[0]) * 1000) if nums else 1000
            cpp_lines.append(f"  delay({ms});")
        elif "high" in line_lower or "value(1)" in line_lower or "glow" in line_lower:
            for p in unique_pins:
                cpp_lines.append(f"  digitalWrite({p}, HIGH);")
        elif "low" in line_lower or "value(0)" in line_lower or "off" in line_lower:
            for p in unique_pins:
                cpp_lines.append(f"  digitalWrite({p}, LOW);")

    cpp_lines.extend(["}", ""])
    return "\n".join(cpp_lines)


def convert_to_micropython(cleaned_lines, unique_pins):
    """Generates pure MicroPython payload that your ESP chip CAN execute"""
    py_lines = [
        "from machine import Pin",
        "import time",
        ""
    ]
    for pin in unique_pins:
        py_lines.append(f"pin_{pin} = Pin({pin}, Pin.OUT)")
    py_lines.append("")

    for line in cleaned_lines:
        line_lower = line.lower()
        if "sleep" in line_lower or "delay" in line_lower:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            secs = float(nums[0]) if nums else 1.0
            py_lines.append(f"time.sleep({secs:.1f})")
        elif "high" in line_lower or "value(1)" in line_lower or "glow" in line_lower:
            for p in unique_pins:
                py_lines.append(f"pin_{p}.value(1)")
        elif "low" in line_lower or "value(0)" in line_lower or "off" in line_lower:
            for p in unique_pins:
                py_lines.append(f"pin_{p}.value(0)")

    return "\n".join(py_lines)


@app.route("/", methods=["GET"])
def home():
    """Web interface displaying BOTH C++ and MicroPython formats"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP Code Engine</title>
        <style>
            body { font-family: sans-serif; padding: 20px; background: #0f172a; color: #f8fafc; }
            textarea { width: 100%; height: 150px; background: #1e293b; color: #38bdf8; padding: 10px; border-radius: 6px; }
            button { background: #0284c7; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
            pre { background: #1e293b; padding: 15px; color: #4ade80; border-radius: 6px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h2>ESP Transpiler & Dynamic Output Engine</h2>
        <textarea id="code">digitalWrite(5, HIGH)\ntime.sleep(1.0)\ndigitalWrite(5, LOW)</textarea><br><br>
        <button onclick="transpile()">Generate Code</button>
        
        <h3>Generated C++ (For Display):</h3>
        <pre id="cpp_out">Waiting...</pre>
        
        <h3>Executable MicroPython Payload (Sent to ESP Chip):</h3>
        <pre id="py_out">Waiting...</pre>

        <script>
            async function transpile() {
                const input = document.getElementById('code').value;
                const res = await fetch('/transpile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: input })
                });
                const data = await res.json();
                document.getElementById('cpp_out').textContent = data.cpp_code;
                document.getElementById('py_out').textContent = data.result;
            }
        </script>
    </body>
    </html>
    """

@app.route("/transpile", methods=["POST"])
def transpile():
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "")

    lines = raw_code.splitlines()
    cleaned_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("//")]

    found_pins = re.findall(r'\b\d+\b', raw_code)
    unique_pins = [p for p in found_pins if int(p) <= 40] or ["5", "0", "14"]

    cpp_payload = convert_to_cpp(cleaned_lines, unique_pins)
    micropython_payload = convert_to_micropython(cleaned_lines, unique_pins)

    return jsonify({
        "status": "success",
        "cpp_code": cpp_payload,      # Displayed for C++ lovers
        "result": micropython_payload  # Sent directly to ESP board to execute!
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
        
