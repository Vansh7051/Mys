from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os, re, ast

app = Flask(__name__)
CORS(app)

latest_instructions = ""

# =========================================================
# STEP 1: AST UNIVERSAL COMPILER
# Converts complex Python (loops, lists, vars) into 
# the explicit DIGITALWRITE & DELAY format.
# =========================================================
class UniversalHardwareCompiler(ast.NodeVisitor):
    def __init__(self):
        self.variables = {}
        self.output_commands = []

    def evaluate_expr(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return self.variables.get(node.id, node.id)
        elif isinstance(node, ast.List):
            return [self.evaluate_expr(elt) for elt in node.elts]
        elif isinstance(node, ast.JoinedStr):
            return "".join(str(self.evaluate_expr(v)) for v in node.values)
        elif isinstance(node, ast.FormattedValue):
            return self.evaluate_expr(node.value)
        return None

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                val = self.evaluate_expr(node.value)
                self.variables[target.id] = val
        self.generic_visit(node)

    def visit_Call(self, node):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}"

        if func_name.lower() in ["digitalwrite", "digital_write"]:
            if len(node.args) >= 2:
                pin_val = str(self.evaluate_expr(node.args[0]))
                state_val = str(self.evaluate_expr(node.args[1])).upper()
                state_val = "HIGH" if state_val in ["1", "TRUE", "HIGH"] else "LOW"
                self.output_commands.append(f'DIGITALWRITE("{pin_val}", {state_val})')

        elif func_name.lower() in ["delay", "sleep", "time.sleep"]:
            if len(node.args) >= 1:
                val = float(self.evaluate_expr(node.args[0]))
                ms = int(val * 1000) if "sleep" in func_name.lower() and val < 100 else int(val)
                self.output_commands.append(f'DELAY({ms})')

        self.generic_visit(node)

    def visit_For(self, node):
        iter_obj = self.evaluate_expr(node.iter)
        if isinstance(node.iter, ast.Call) and getattr(node.iter.func, 'id', '') == 'range':
            args = [self.evaluate_expr(a) for a in node.iter.args]
            iter_obj = list(range(*args))

        if isinstance(node.target, ast.Name) and isinstance(iter_obj, list):
            var_name = node.target.id
            for item in iter_obj:
                self.variables[var_name] = item
                for stmt in node.body:
                    self.visit(stmt)


def compile_complex_python_to_format(user_python_code):
    """Parses any complex Python code into explicit Notepad-style commands."""
    try:
        parsed_ast = ast.parse(user_python_code)
        compiler = UniversalHardwareCompiler()
        compiler.visit(parsed_ast)
        
        formatted_script = ["WHILE TRUE:"]
        for cmd in compiler.output_commands:
            formatted_script.append(f"    {cmd}")
        return "\n".join(formatted_script)
        
    except Exception:
        # Fallback line-by-line parser if code contains custom pseudo-syntax
        lines = user_python_code.split('\n')
        fallback_cmds = []
        for line in lines:
            if "digitalWrite" in line or "digital_write" in line or "DIGITALWRITE" in line:
                matches = re.findall(r'["\']?(.*?)["\']?\s*,\s*(HIGH|LOW|1|0)', line, re.IGNORECASE)
                if matches:
                    pin, state = matches[0]
                    state = "HIGH" if state.upper() in ["HIGH", "1"] else "LOW"
                    fallback_cmds.append(f'DIGITALWRITE("{pin.strip()}", {state})')
            elif "sleep" in line or "delay" in line or "DELAY" in line:
                nums = re.findall(r'\d+\.?\d*', line)
                if nums:
                    val = float(nums[0])
                    ms = int(val * 1000) if ("sleep" in line.lower() and val < 100) else int(val)
                    fallback_cmds.append(f'DELAY({ms})')

        formatted_script = ["WHILE TRUE:"]
        for cmd in fallback_cmds:
            formatted_script.append(f"    {cmd}")
        return "\n".join(formatted_script)


# =========================================================
# STEP 2: HARDWARE TRANSPILER
# Converts explicit commands into binary instruction string.
# =========================================================
def transpile_python_to_instructions(formatted_code):
    commands = []
    pin_map = {
        "D0": 16, "D1": 5, "D2": 4, "D3": 0, "D4": 2, 
        "D5": 14, "D6": 12, "D7": 13, "D8": 15
    }

    lines = formatted_code.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith("WHILE"):
            continue

        if "DELAY(" in line:
            try:
                ms = int(re.search(r'DELAY\((\d+)\)', line).group(1))
                commands.append(f"DELAY:{ms}")
            except:
                pass

        elif "DIGITALWRITE(" in line:
            state = "1" if "HIGH" in line else "0"
            found_pin = None
            
            # Check for ESP pin labels (e.g. D1, D3)
            for p_label, p_num in pin_map.items():
                if f'"{p_label}"' in line or f"'{p_label}'" in line:
                    found_pin = p_num
                    break
            
            # Check for raw numeric GPIO pins (e.g. GPIO 12, 14, 22)
            if found_pin is None:
                numbers = re.findall(r'\d+', line)
                if numbers:
                    found_pin = int(numbers[0])

            if found_pin is not None:
                commands.append(f"WRITE:{found_pin}:{state}")

    return ";".join(commands)


# =========================================================
# STEP 3: FLASK ROUTES & PORTAL
# =========================================================
HTML_PORTAL = """
<!DOCTYPE html>
<html>
<head>
    <title>Universal ESP Code Sender</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow">
        <h1 class="text-xl font-bold mb-4">Universal ESP Code Transpiler</h1>
        <textarea id="code" class="w-full h-48 border p-3 font-mono text-sm rounded mb-4" placeholder="Write any Python code here..."></textarea>
        <button onclick="sendCode()" class="bg-black text-white px-6 py-2 rounded font-bold">EXECUTE ON ESP</button>
        
        <div class="mt-6">
            <h2 class="text-sm font-bold text-gray-700 mb-2">Compiled Intermediate Format:</h2>
            <pre id="compiled_format" class="bg-gray-900 text-green-400 p-3 rounded font-mono text-xs h-32 overflow-y-auto"></pre>
        </div>
        <p id="status" class="mt-4 text-sm font-mono text-gray-600"></p>
    </div>
    <script>
        async function sendCode() {
            const code = document.getElementById('code').value;
            document.getElementById('status').innerText = "Compiling & deploying to ESP...";
            const res = await fetch('/transpile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_code: code})
            });
            const data = await res.json();
            document.getElementById('compiled_format').innerText = data.formatted_code;
            document.getElementById('status').innerText = "Status: Code deployed to ESP successfully!";
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
    
    # Step 1: Unroll complex Python into explicit script format
    formatted_code = compile_complex_python_to_format(user_code)
    
    # Step 2: Convert script format to hardware instruction stream
    latest_instructions = transpile_python_to_instructions(formatted_code)
    
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
            
