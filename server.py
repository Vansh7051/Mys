from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def run_transpiler_engine(python_code):
    if not python_code or not python_code.strip():
        return {"status": "error", "message": "Please enter some code first"}
        
    # Simple original translation layout
    clean_input = python_code.strip()
    if clean_input.startswith('print("') and clean_input.endswith('")'):
        inner_text = clean_input[7:-2]
        mock_cpp_output = f'#include <iostream>\n\nint main() {{\n    std::cout << "{inner_text}" << std::endl;\n    return 0;\n}}'
    else:
        mock_cpp_output = f'#include <iostream>\n\nint main() {{\n    // Translated:\n    // {clean_input}\n    return 0;\n}}'
        
    return {"status": "success", "cpp_code": mock_cpp_output}

@app.route('/transpile', methods=['POST'])
def handle_api_request():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No JSON received"}), 400
            
        # Match the "user_code" key from the website
        user_python_input = data.get("user_code", "")
        result = run_transpiler_engine(user_python_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
        
