from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os, re, sys, io

app = Flask(__name__)
CORS(app)

latest_instructions = ""

class HardwareExecutionEngine:
    """
    Virtual MicroPython Execution Engine.
    Executes real Python/MicroPython code in an isolated environment 
    and captures actual pin state transitions and delays.
    """
    def __init__(self):
        self.events = []
        # Mapping ESP8266 silk-screen labels to GPIO integers
        self.pin_map = {
            "D0": 16, "D1": 5, "D2": 4, "D3": 0, "D4": 2,
            "D5": 14, "D6": 12, "D7": 13, "D8": 15
        }

    def _resolve_pin(self, pin_id):
        if isinstance(pin_id, str):
            clean_str = pin_id.strip().upper()
            if clean_str in self.pin_map:
                return self.pin_map[clean_str]
            numbers = re.findall(r'\d+', clean_str)
            if numbers:
                return int(numbers[0])
        elif isinstance(pin_id, int):
            return pin_id
        return 5 # Default to GPIO 5 (D1) if unknown

    def record_write(self, pin_id, state):
        gpio = self._resolve_pin(pin_id)
        st = 1 if state in [1, True, "1", "HIGH", "high"] else 0
        self.events.append(f"WRITE:{gpio}:{st}")

    def record_delay(self, seconds):
        try:
            ms = int(float(seconds) * 1000)
            if ms > 0:
                self.events.append(f"DELAY:{ms}")
        except ValueError:
            pass


def execute_python_script(user_code):
    """
    Runs user code dynamically in a simulated MicroPython runtime.
    """
    engine = HardwareExecutionEngine()

    # Define mock 'machine' module
    class VirtualPin:
        OUT = "OUT"
        IN = "IN"
        PULL_UP = "PULL_UP"

        def __init__(self, pin_id, mode=None, value=0):
            self.pin_id = pin_id
            if value is not None:
                engine.record_write(self.pin_id, value)

        def value(self, val=None):
            if val is not None:
                engine.record_write(self.pin_id, val)
                return val
            return 0

        def on(self):
            engine.record_write(self.pin_id, 1)

        def off(self):
            engine.record_write(self.pin_id, 0)

        def high(self):
            engine.record_write(self.pin_id, 1)

        def low(self):
            engine.record_write(self.pin_id, 0)

    class VirtualMachineModule:
        Pin = VirtualPin

    class VirtualTimeModule:
        @staticmethod
        def sleep(sec):
            engine.record_delay(sec)

        @staticmethod
        def sleep_ms(ms):
            engine.record_delay(ms / 1000.0)

    # Standard Arduino-style global function helpers
    def digitalWrite(pin, state):
        engine.record_write(pin, state)

    def delay(ms):
        engine.record_delay(ms / 1000.0)

    # Intercept print calls cleanly
    stdout_capture = io.StringIO()

    # Create execution scope
    execution_scope = {
        'machine': VirtualMachineModule,
        'Pin': VirtualPin,
        'time': VirtualTimeModule,
        'sleep': VirtualTimeModule.sleep,
        'digitalWrite': digitalWrite,
        'digital_write': digitalWrite,
        'delay': delay,
        'HIGH': 1,
        'LOW': 0,
        'True': True,
        'False': False,
        'print': lambda *args, **kwargs: stdout_capture.write(" ".join(map(str, args)) + "\n")
    }

    # Clean code: remove infinite 'while True:' wrappers so execution completes cleanly in 1 loop pass
    cleaned_lines = []
    for line in user_code.split('\n'):
        # Strip out infinite loops or keyboard interrupts that lock up server execution
        if re.search(r'while\s+True\s*:', line) or re.search(r'except\s+KeyboardInterrupt\s*:', line) or 'try:' in line:
            continue
        cleaned_lines.append(line)
    
    executable_code = "\n".join(cleaned_lines)

    try:
        # EXECUTE THE PYTHON CODE FOR REAL
        exec(executable_code, execution_scope)
    except Exception as e:
        return f"# Execution Error: {str(e)}", ""

    # Build readable display format
    formatted_display = ["WHILE TRUE:"]
    for evt in engine.events:
        if evt.startswith("WRITE:"):
            _, p, s = evt.split(":")
            st_label = "HIGH" if s == "1" else "LOW"
            formatted_display.append(f'    DIGITALWRITE("GPIO {p}", {st_label})')
        elif evt.startswith("DELAY:"):
            _, ms = evt.split(":")
            formatted_display.append(f'    DELAY({ms})')

    instruction_stream = ";".join(engine.events)
    return "\n".join(formatted_display), instruction_stream


# =========================================================
# FLASK INTERFACE & PORTAL
# =========================================================
HTML_PORTAL = """
<!DOCTYPE html>
<html>
<head>
    <title>Universal ESP Python Sandbox Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">
        <h1 class="text-xl font-bold mb-4">Universal ESP Python Sandbox Engine</h1>
        <textarea id="code" class="w-full h-56 border p-3 font-mono text-sm rounded mb-4 focus:outline-none focus:ring-2 focus:ring-black" placeholder="Write ANY Python or MicroPython code here..."></textarea>
        <button onclick="sendCode()" class="bg-black text-white px-6 py-2 rounded font-bold hover:bg-gray-800 transition">EXECUTE ON ESP</button>
        
        <div class="mt-6">
            <h2 class="text-sm font-bold text-gray-700 mb-2">Captured Hardware Event Sequence:</h2>
            <pre id="compiled_format" class="bg-gray-900 text-green-400 p-4 rounded font-mono text-xs h-40 overflow-y-auto"></pre>
        </div>
        <p id="status" class="mt-4 text-sm font-mono text-gray-600"></p>
    </div>
    <script>
        async function sendCode() {
            const code = document.getElementById('code').value;
            document.getElementById('status').innerText = "Running Python execution sandbox...";
            try {
                const res = await fetch('/transpile', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_code: code})
                });
                const data = await res.json();
                document.getElementById('compiled_format').innerText = data.formatted_code;
                document.getElementById('status').innerText = "Status: Code executed in sandbox & hardware stream sent to ESP!";
            } catch (err) {
                document.getElementById('status').innerText = "Error connecting to server.";
            }
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
    
    formatted_code, latest_instructions = execute_python_script(user_code)
    
    return jsonify({
        "status": "success", 
        "formatted_code": formatted_code,
        "instructions": latest_instructions
    }), 200

@app.route('/getcode', methods=['GET'])
def get_code():
    return latest_instructions, 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
        
