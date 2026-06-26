from flask import Flask, request, jsonify
import re

app = Flask(__name__)

def run_transpiler_engine(python_code):
    """
    This is your exact standalone logic engine, stripped of all desktop 
    window styling. It processes the code entirely in the server memory.
    """
    if not python_code.strip():
        return {"status": "error", "message": "Please enter a Python command first"}
        
    errors = []
    lines = python_code.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
        
    # 1. Balance validation checks
    if python_code.count("(") != python_code.count(")"):
        errors.append("Syntax Error: Unbalanced parenthesis detected. Missing matching parenthesis.")
    if python_code.count("[") != python_code.count("]"):
        errors.append("Syntax Error: Unbalanced brackets '[ ]' detected.")
    if python_code.count("{") != python_code.count("}"):
        errors.append("Syntax Error: Unbalanced curly brackets '{ }' detected.")

    # 2. String literal boundary check
    inside_string = False
    string_char = ""
    for i in range(len(python_code)):
        char = python_code[i]
        prev_char = python_code[i - 1] if i > 0 else ""
        if (char == '"' or char == "'") and prev_char != '\\':
            if not inside_string:
                inside_string = True
                string_char = char
            elif string_char == char:
                inside_string = False
                
    if inside_string:
        errors.append("Syntax Error: Unterminated string literal detected.")

    # 3. Line-by-line syntax validation engine
    for idx in range(len(lines)):
        original_line = lines[idx]
        trimmed_line = original_line.strip()
        line_num = idx + 1
        
        if not trimmed_line or trimmed_line.startswith("#"):
            continue
            
        code_line = trimmed_line
        inside_str = False
        quote_char = ""
        hash_idx = -1
        
        for c in range(len(trimmed_line)):
            char = trimmed_line[c]
            prev_char = trimmed_line[c - 1] if c > 0 else ""
            if (char == '"' or char == "'") and prev_char != "\\":
                if not inside_str:
                    inside_str = True
                    quote_char = char
                elif quote_char == char:
                    inside_str = False
            if char == '#' and not inside_str:
                hash_idx = c
                break
                
        if hash_idx != -1:
            code_line = trimmed_line[:hash_idx].strip()
            
        if not code_line:
            continue
            
        # Capitalization validation rules
        first_word = re.split(r'[^a-zA-Z_0-9]', code_line)[0]
        capitalized_keywords = {
            "Print": "print", "If": "if", "Elif": "elif", "Else": "else",
            "While": "while", "For": "for", "Return": "return", "Pass": "pass",
            "Break": "break", "Continue": "continue", "Class": "class", "Def": "def"
        }
        
        if first_word in capitalized_keywords:
            errors.append(f"NameError on line {line_num}: Name '{first_word}' is not defined. Did you mean '{capitalized_keywords[first_word]}'?")
            continue

        # Block syntax checks
        last_char = code_line[-1]
        starts_with_keyword_block = (
            code_line.startswith("if ") or code_line.startswith("if(") or
            code_line.startswith("elif ") or code_line.startswith("elif(") or
            code_line == "else" or code_line.startswith("else ") or
            code_line.startswith("while ") or code_line.startswith("while(") or
            code_line.startswith("for ") or code_line.startswith("for(") or
            code_line.startswith("def ") or code_line.startswith("class ")
        )
        
        if starts_with_keyword_block:
            if last_char != ":":
                errors.append(f"SyntaxError on line {line_num}: expected ':' at the end of block statement.")
                continue
            if code_line.startswith("for ") and " in " not in code_line:
                errors.append(f"SyntaxError on line {line_num}: 'for' loop missing 'in' clause.")
                continue

    # Return compilation report
    if errors:
        return {"status": "syntax_error", "errors": errors}
    
    # If code passes all checks, simulate the conversion output template
    # (This replaces your text panels from the desktop app)
    mock_cpp_output = "// Verified Conversion\n#include <iostream>\nint main() {\n    // Server processed translation successfully\n    return 0;\n}"
    return {"status": "success", "cpp_code": mock_cpp_output}


# The Server Gate: Connects your web interface data to the logic above
@app.route('/transpile', methods=['POST'])
def handle_api_request():
    data = request.get_json()
    user_python_input = data.get("user_code", "")
    
    # Run the engine
    result = run_transpiler_engine(user_python_input)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
  
