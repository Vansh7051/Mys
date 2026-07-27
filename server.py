from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Enables communication from frontend UI

# 1. Global variable to store latest converted code for the microcontroller
latest_cpp_code = "// No code transpiled yet."

def transpile_python_to_cpp(py_code):
    """Simple Transpiler Logic"""
    cpp_lines = [
        "#include <iostream>",
        "using namespace std;",
        "",
        "int main() {"
    ]
    for line in py_code.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith("print(") and line.endswith(")"):
            content = line[6:-1]
            cpp_lines.append(f'    cout << {content} << endl;')
        elif "=" in line and not line.startswith("if"):
            var, val = line.split("=", 1)
            cpp_lines.append(f'    auto {var.strip()} = {val.strip()};')
        else:
            cpp_lines.append(f'    // Unparsed line: {line}')
            
    cpp_lines.append("    return 0;")
    cpp_lines.append("}")
    return "\n".join(cpp_lines)

# Embedded Web UI
HTML_PORTAL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyToCpp - Live Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#fafaf8] text-[#1c1c1b] font-sans min-h-screen flex flex-col justify-between">

    <header class="bg-white border-b border-[#e7e5e4] px-6 py-4 flex justify-between items-center shadow-sm">
        <div class="flex items-center gap-2">
            <div class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
            <span class="text-xs font-bold tracking-wider uppercase font-mono text-emerald-600">SERVER STATUS: ONLINE</span>
        </div>
    </header>

    <main class="max-w-2xl w-full mx-auto p-6 flex-grow flex flex-col justify-center gap-6">
        <div class="text-center mb-2">
            <h1 class="text-2xl font-light text-[#0c0a09]">Python to C++ Transpiler</h1>
            <p class="text-xs text-[#78716c] mt-1">Connected live to your pipeline endpoint.</p>
        </div>

        <div class="bg-white border border-[#e7e5e4] rounded-xl overflow-hidden shadow-sm">
            <div class="bg-[#fcfcfb] border-b border-[#e7e5e4] px-4 py-2 flex justify-between items-center">
                <span class="text-xs font-bold text-[#a8a29e] font-mono">📄 INPUT PYTHON</span>
            </div>
            <textarea id="myTextArea" class="w-full h-40 p-4 font-mono text-sm bg-white text-[#1c1c1b] focus:outline-none resize-none" placeholder="Type your Python code here...&#10;Example: print(&quot;hello&quot;)"></textarea>
            <div class="bg-[#fcfcfb] border-t border-[#f5f5f4] px-4 py-3 flex justify-end">
                <button id="mySubmitButton" class="bg-[#1c1c1b] hover:bg-black text-white text-xs font-bold px-6 py-2.5 rounded-lg tracking-wider uppercase transition-all shadow-sm">
                    CONVERT TO C++
                </button>
            </div>
        </div>

        <div class="flex flex-col gap-2">
            <div class="flex justify-between items-center">
                <span class="text-xs font-bold text-[#a8a29e] font-mono">💻 C++ OUTPUT</span>
                <span id="statusPill" class="text-[10px] font-bold bg-white text-[#78716c] border border-[#e7e5e4] px-2 py-0.5 rounded uppercase tracking-wider font-mono">Idle</span>
            </div>
            <div class="bg-white border border-[#e7e5e4] rounded-xl overflow-hidden shadow-sm">
                <pre id="outputScreen" class="p-4 bg-[#fbfbfa] text-[#1c1c1b] font-mono text-xs min-h-[120px] whitespace-pre-wrap break-all">Waiting for instructions...</pre>
            </div>
        </div>
    </main>

    <script>
        const TARGET_SERVER_URL = "/transpile";

        async function processTranspilation() {
            const userInputText = document.getElementById('myTextArea').value; 
            const outputScreen = document.getElementById('outputScreen');
            const statusPill = document.getElementById('statusPill');

            if (!userInputText.trim()) {
                alert("Please type some Python code first!");
                return;
            }

            statusPill.textContent = "Processing...";
            statusPill.className = "text-[10px] font-bold bg-amber-50 text-amber-600 border border-amber-200 px-2 py-0.5 rounded uppercase tracking-wider font-mono";
            outputScreen.textContent = "Converting Python code...";

            try {
                const response = await fetch(TARGET_SERVER_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_code: userInputText })
                });

                const result = await response.json();

                if (result.status === "success") {
                    statusPill.textContent = "Success";
                    statusPill.className = "text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-200 px-2 py-0.5 rounded uppercase tracking-wider font-mono";
                    outputScreen.textContent = result.cpp_code;
                } else {
                    statusPill.textContent = "Error";
                    statusPill.className = "text-[10px] font-bold bg-red-50 text-red-600 border border-red-200 px-2 py-0.5 rounded uppercase tracking-wider font-mono";
                    outputScreen.textContent = result.message || "An error occurred.";
                }

            } catch (error) {
                statusPill.textContent = "Error";
                statusPill.className = "text-[10px] font-bold bg-red-100 text-red-700 border border-red-300 px-2 py-0.5 rounded uppercase tracking-wider font-mono";
                outputScreen.textContent = "Could not connect to server.";
            }
        }

        document.getElementById('mySubmitButton').addEventListener('click', processTranspilation);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    """Serves the Web UI"""
    return render_template_string(HTML_PORTAL)

@app.route('/transpile', methods=['POST'])
def transpile():
    """Called by Website: Transpiles Python and stores C++ in memory"""
    global latest_cpp_code
    data = request.get_json(silent=True) or {}
    user_code = data.get('user_code', '')

    if not user_code:
        return jsonify({"status": "error", "message": "No Python code provided"}), 400

    latest_cpp_code = transpile_python_to_cpp(user_code)

    return jsonify({
        "status": "success",
        "cpp_code": latest_cpp_code
    }), 200

@app.route('/getcode', methods=['GET'])
def get_code():
    """Called by ESP8266/ESP32: Returns the stored C++ code"""
    return jsonify({
        "status": "success",
        "cpp_code": latest_cpp_code
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
            
