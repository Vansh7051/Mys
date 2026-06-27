from flask import Flask, request, jsonify
from flask_cors import CORS
import re

# 💡 GUNICORN IS LOOKING FOR THIS EXACT LINE:
app = Flask(__name__)
# This allows your HTML file to communicate securely
CORS(app)

def run_transpiler_engine(python_code):
    if not python_code or not python_code.strip():
        return {"status": "error", "message": "Please enter a Python command first"}
        
    errors = []
    lines = python_code.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
        
    # 1. Bracket Balance Validation
    code_sans_strings = re.sub(r'(".*?"|\'.*?\')', '', python_code)
    if code_sans_strings.count("(") != code_sans_strings.count(")"):
        errors.append("Syntax Error: Unbalanced parenthesis detected.")
    if code_sans_strings.count("[") != code_sans_strings.count("]"):
        errors.append("Syntax Error: Unbalanced brackets '[ ]' detected.")
    if code_sans_strings.count("{") != code_sans_strings.count("}"):
        errors.append("Syntax Error: Unbalanced curly brackets '{ }' detected.")

    # 2. Line-by-line syntax engine logic
    lower_code = python_code.lower()
    if "green" in lower_code or "led_green" in lower_code:
        errors.append("Logic Error: You configured the GREEN LED, but the assignment requires the RED LED to glow.")
    if "red" not in lower_code and "led_red" not in lower_code:
        errors.append("Configuration Error: Missing the RED LED target variable or setup connection statement.")
    if "high" not in lower_code and "on" not in lower_code and "true" not in lower_code:
        errors.append("Execution Error: You set up the LED connection, but you never sent power to turn it ON.")

    for idx in range(len(lines)):
        trimmed_line = lines[idx].strip()
        line_num = idx + 1
        
        if not trimmed_line or trimmed_line.startswith("#"):
            continue
            
        first_word = re.split(r'[^a-zA-Z_0-9]', trimmed_line)[0]
        capitalized_keywords = {
            "Print": "print", "If": "if", "Elif": "elif", "Else": "else",
            "While": "while", "For": "for", "Def": "def"
        }
        
        if first_word in capitalized_keywords:
            errors.append(f"NameError on line {line_num}: Did you mean '{capitalized_keywords[first_word]}'?")
            continue

        starts_with_keyword_block = (
            trimmed_line.startswith("if ") or trimmed_line.startswith("if(") or
            trimmed_line.startswith("elif ") or trimmed_line.startswith("elif(") or
            trimmed_line.startswith("else") or trimmed_line.startswith("while ") or
            trimmed_line.startswith("for ") or trimmed_line.startswith("def ")
        )
        
        if starts_with_keyword_block and not trimmed_line.endswith(":"):
            errors.append(f"SyntaxError on line {line_num}: expected ':' at the end of block statement.")

    if errors:
        return {"status": "syntax_error", "errors": errors}
    
    clean_input = python_code.strip()
    mock_cpp_output = (
        "#include <iostream>\n"
        "// Hardware Pin Mapping Verified\n"
        "int main() {\n"
        "    pinMode(RED_LED_PIN, OUTPUT);\n"
        "    digitalWrite(RED_LED_PIN, HIGH); // Red LED glowing perfectly\n"
        "    return 0;\n"
        "}"
    )
        
    return {"status": "success", "cpp_code": mock_cpp_output}

@app.route('/transpile', methods=['POST'])
def handle_api_request():
    try:
        data = request.get_json()
        print("--- DEBUG: RECEIVED FROM WEBSITE ---", data)
        
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received"}), 400
            
        user_python_input = data.get("user_code", "")
        result = run_transpiler_engine(user_python_input)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
