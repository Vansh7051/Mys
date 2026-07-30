import os
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

def sanitize_and_transpile(raw_code: str) -> str:
    """
    Sanitizes raw hardware code/commands, strips unsupported imports, 
    removes C++ artifacts, and outputs valid MicroPython for ESP boards.
    """
    if not raw_code or not raw_code.strip():
        return "from machine import Pin\nimport time\n"

    lines = raw_code.splitlines()
    cleaned_lines = []
    in_cpp_block = False

    for line in lines:
        stripped = line.strip()

        # 1. Filter / Fix Import Statements
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Strip out unsupported desktop/python imports (like os, sys, re, math)
            # Only keep valid MicroPython hardware imports
            if any(mod in stripped for mod in ["machine", "time", "utime", "urequests", "ujson", "uasyncio"]):
                cleaned_lines.append(stripped)
            continue

        # 2. Filter C++ / Arduino Headers & Blocks
        if stripped.startswith("#include") or "void setup" in stripped or "void loop" in stripped:
            in_cpp_block = True
            continue
        if stripped == "}" and in_cpp_block:
            in_cpp_block = False
            continue
        if in_cpp_block:
            continue

        # 3. Strip C++ inline comments
        if "//" in stripped:
            stripped = stripped.split("//")[0].strip()

        # 4. Fix malformed sleep dots: time.sleep(.) -> time.sleep(1.0)
        stripped = re.sub(r'time\.sleep\(\s*\.\s*\)', 'time.sleep(1.0)', stripped)

        if stripped:
            cleaned_lines.append(stripped)

    clean_text = "\n".join(cleaned_lines)

    # 5. Safe Pin Extraction
    explicit_pins = re.findall(r'(?:pin_|Pin\(|digitalWrite\(\s*)(\d+)', clean_text, re.IGNORECASE)
    unique_pins = []
    for p in explicit_pins:
        if p not in unique_pins and int(p) <= 40:
            unique_pins.append(p)

    # Default fallback channels if no pin is specified
    if not unique_pins:
        unique_pins = ["5", "0", "14", "13", "2", "1"]

    # 6. Build MicroPython Output Header
    output_lines = [
        "from machine import Pin",
        "import time",
        ""
    ]
    
    # Initialize Pin Objects
    for pin in unique_pins:
        output_lines.append(f"pin_{pin} = Pin({pin}, Pin.OUT)")
    output_lines.append("")

    # 7. Convert Action Statements
    for line in cleaned_lines:
        line_lower = line.lower()

        # Handle Delays
        if "sleep" in line_lower or "delay" in line_lower or "wait" in line_lower:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            if nums:
                val = float(nums[0])
                secs = val / 1000.0 if val > 100 else val
                secs = max(0.1, secs)
            else:
                secs = 1.0  # Default safe delay
            output_lines.append(f"time.sleep({secs:.1f})")

        # Handle Turning Pins ON / HIGH / GLOW
        elif "high" in line_lower or "value(1)" in line_lower or "glow" in line_lower or ("digitalwrite" in line_lower and ("1" in line_lower or "true" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                output_lines.append(f"pin_{pin}.value(1)")

        # Handle Turning Pins OFF / LOW
        elif "low" in line_lower or "value(0)" in line_lower or "off" in line_lower or ("digitalwrite" in line_lower and ("0" in line_lower or "false" in line_lower)):
            target_pins = re.findall(r'\b\d+\b', line)
            pins_to_set = [p for p in target_pins if p in unique_pins] or unique_pins
            for pin in pins_to_set:
                output_lines.append(f"pin_{pin}.value(0)")

    return "\n".join(output_lines)


# ------------------------------------------------------------------------------
# REST API ENDPOINTS
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "Offline MicroPython Transpiler Server is Active and Running!"

@app.route("/transpile", methods=["POST"])
def transpile():
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "") or data.get("raw_code", "")

    # Fallback to handle raw text string input
    if not raw_code and request.data:
        raw_code = request.data.decode("utf-8", errors="ignore")

    result_code = sanitize_and_transpile(raw_code)
    return jsonify({
        "status": "success",
        "result": result_code
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("==================================================")
    print("  RESTORED TRANSPILER SERVER RUNNING              ")
    print(f"  URL: http://0.0.0.0:{port}                     ")
    print("==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
    
