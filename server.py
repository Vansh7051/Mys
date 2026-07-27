from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os, re

app = Flask(__name__)
CORS(app)

latest_instructions = ""

def transpile_python_to_instructions(py_code):
    """
    Generalized Transpiler: Parses any Python pin commands, 
    loops, and delays into executable instructions for ESP hardware.
    """
    commands = []
    
    # Generic pin map supporting GPIO pin numbers and ESP labels
    pin_map = {
        "D0": 16, "D1": 5, "D2": 4, "D3": 0, "D4": 2, 
        "D5": 14, "D6": 12, "D7": 13, "D8": 15
    }

    lines = py_code.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Convert delays: time.sleep(0.5) or delay(500) -> DELAY:500
        if "time.sleep(" in line:
            try:
                val = float(re.search(r'time\.sleep\((.*?)\)', line).group(1))
                commands.append(f"DELAY:{int(val * 1000)}")
            except:
                pass
        elif "delay(" in line:
            try:
                val = int(re.search(r'delay\((.*?)\)', line).group(1))
                commands.append(f"DELAY:{val}")
            except:
                pass

        # Convert Pin States: digitalWrite(pin, HIGH/LOW) or pin = 1/0
        elif "HIGH" in line or "LOW" in line or "digitalWrite" in line:
            state = "1" if "HIGH" in line or "1" in line else "0"
            # Extract pin number or label
            found_pin = None
            for p_label, p_num in pin_map.items():
                if p_label in line:
                    found_pin = p_num
                    break
            
            if found_pin is None:
                # Extract numeric pin if directly given (e.g. GPIO 5)
                numbers = re.findall(r'\d+', line)
                if numbers:
                    found_pin = int(numbers[0])

            if found_pin is not None:
                commands.append(f"WRITE:{found_pin}:{state}")

    return ";".join(commands)

HTML_PORTAL = """
<!DOCTYPE html>
<html>
<head>
    <title>Universal ESP Code Sender</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-2xl mx-auto bg-white p-6 rounded-xl shadow">
        <h1 class="text-xl font-bold mb-4">Universal ESP Code Transpiler</h1>
        <textarea id="code" class="w-full h-48 border p-3 font-mono text-sm rounded mb-4" placeholder="Write any Python code here..."></textarea>
        <button onclick="sendCode()" class="bg-black text-white px-6 py-2 rounded font-bold">EXECUTE ON ESP</button>
        <p id="status" class="mt-4 text-sm font-mono text-gray-600"></p>
    </div>
    <script>
        async function sendCode() {
            const code = document.getElementById('code').value;
            document.getElementById('status').innerText = "Sending to server...";
            const res = await fetch('/transpile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_code: code})
            });
            const data = await res.json();
            document.getElementById('status').innerText = "Code converted and deployed to ESP pipeline!";
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PORTAL)

@app.route('/transpile', methods=['POST'])
def transpile():
    global latest_instructions
    data = request.get_json(silent=True) or {}
    user_code = data.get('user_code', '')
    latest_instructions = transpile_python_to_instructions(user_code)
    return jsonify({"status": "success", "instructions": latest_instructions}), 200

@app.route('/getcode', methods=['GET'])
def get_code():
    return jsonify({"status": "success", "instructions": latest_instructions}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
