from flask import Flask, request, jsonify
import re

app = Flask(__name__)

def run_transpiler_engine(python_code):
    if not python_code or not python_code.strip():
        return {"status": "error", "message": "Please enter a Python command first"}
        
    errors = []
    lines = python_code.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
        
    # 1. Parenthesis and Bracket Balance Validation
    if python_code.count("(") != python_code.count(")"):
        errors.append("Syntax Error: Unbalanced parenthesis detected.")
    if python_code.count("[") != python_code.count("]"):
        errors.append("Syntax Error: Unbalanced brackets '[ ]' detected.")
    if python_code.count("{") != python_code.count("}"):
        errors.append("Syntax Error: Unbalanced curly brackets '{ }' detected.")

    # 2. Line-by-line syntax engine logic
    for idx in range(len(lines)):
        original_line = lines[idx]
        trimmed_line = original_line.strip()
        line_num = idx + 1
        
        if not trimmed_line or trimmed_line.startswith("#"):
            continue
            
        # Capitalization checks
        first_word = re.split(r'[^a-zA-Z_0-9]', trimmed_line)[0]
        capitalized_keywords = {
            "Print": "print", "If": "if", "Elif": "elif", "Else": "else",
            "While": "while", "For": "for", "Def": "def"
        }
        
        if first_word in capitalized_keywords:
            errors.append(f"NameError on line {line_num}: Did you mean '{capitalized_keywords[first_word]}'?")
            continue

        # Missing colon checks
        last_char = trimmed_line[-1]
        starts_with_keyword_block = (
            trimmed_line.startswith("if ") or trimmed_line.startswith("if(") or
            trimmed_line.startswith("elif ") or trimmed_line.startswith("elif(") or
            trimmed_line.startswith("else:") or trimmed_line.startswith("while ") or
            trimmed_line.startswith("for ") or trimmed_line.startswith("def ")
        )
        
        if starts_with_keyword_block and last_char != ":":
            errors.append(f"SyntaxError on line {line_num}: expected ':' at the end of block statement.")

    if errors:
        return {"status": "syntax_error", "errors": errors}
    
    # Simple, functional C++ translation layout dictionary fallback
    clean_input = python_code.strip()
    if clean_input.startswith('print("') and clean_input.endswith('")'):
        inner_text = clean_input[7:-2]
        mock_cpp_output = f'#include <iostream>\n\nint main() {{\n    std::cout << "{inner_text}" << std::endl;\n    return 0;\n}}'
    else:
        mock_cpp_output = f'#include <iostream>\n\nint main() {{\n    // Translated Code Block:\n    // {clean_input}\n    return 0;\n}}'
        
    return {"status": "success", "cpp_code": mock_cpp_output}

@app.route('/transpile', methods=['POST'])
def handle_api_request():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received"}), 400
            
        user_python_input = data.get("user_code", "")
        result = run_transpiler_engine(user_python_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
