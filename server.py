import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def run_transpiler_engine(python_code):
    if not python_code or not python_code.strip():
        return {"status": "error", "message": "❌ Please enter some Python code first!"}

    raw_lines = python_code.splitlines()
    cpp_body_statements = []
    
    # ==========================================
    # 🕵️ CHECK 1: PYTHON LINTING & STRUCTURE AUDIT
    # ==========================================
    for index, line in enumerate(raw_lines):
        trimmed = line.strip()
        line_num = index + 1
        
        if not trimmed or trimmed.startswith('#'):
            continue  
            
        # Flexible Gibberish Check
        if not re.match(r'^[a-zA-Z_0-9][a-zA-Z0-9_\s\.\(\)\"\':\-+=<>!]*$', trimmed):
            if not (trimmed.startswith(('if', 'elif', 'else', 'while', 'for', 'def'))):
                return {
                    "status": "error",
                    "message": f"❌ Python Syntax Error on line {line_num}: Unrecognized gibberish code structure detected."
                }

        # Capitalization mistake handler
        first_word = re.split(r'[^a-zA-Z]', trimmed)[0]
        if first_word in ["Print", "If", "Elif", "Else", "While", "For"]:
            return {
                "status": "error",
                "message": f"❌ Python NameError on line {line_num}: Did you mean lowercase '{first_word.lower()}'? Python is case-sensitive."
            }

        # Unbalanced bracket checking
        if trimmed.count('(') != trimmed.count(')'):
            return {"status": "error", "message": f"❌ Python Syntax Error on line {line_num}: Unbalanced parentheses '( )'."}
        if trimmed.count('[') != trimmed.count(']'):
            return {"status": "error", "message": f"❌ Python Syntax Error on line {line_num}: Unbalanced brackets '[ ]'."}

        # Control block validation (Missing colons)
        if trimmed.startswith(('if ', 'if(', 'elif ', 'elif(', 'while ', 'for ')) and not trimmed.endswith(':'):
            return {
                "status": "error",
                "message": f"❌ Python Syntax Error on line {line_num}: Expected a colon ':' at the end of the statement block."
            }

    # ==========================================
    # ⚙️ STAGE 2: CORE TRANSPILATION LAYER
    # ==========================================
    for line in raw_lines:
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith('#'):
            cpp_body_statements.append(f"    // {trimmed[1:].strip()}")
            continue

        # A. Universal Print Transpilation (Super Flexible Match)
        print_match = re.match(r'^print\s*\((.*)\)$', trimmed)
        if print_match:
            inner_content = print_match.group(1).strip()
            # Check if it has any type of quotes around it
            if (inner_content.startswith('"') and inner_content.endswith('"')) or \
               (inner_content.startswith("'") and inner_content.endswith("'")):
                text = inner_content[1:-1]
                cpp_body_statements.append(f'    std::cout << "{text}" << std::endl;')
            else:
                cpp_body_statements.append(f'    std::cout << {inner_content} << std::endl;')
            continue

        # B. Dynamic Variable Type Mapping Assignment
        if '=' in trimmed and not trimmed.startswith(('if', 'while', 'elif')):
            parts = trimmed.split('=', 1)
            var_name = parts[0].strip()
            var_val = parts[1].strip()
            
            if var_val.isdigit():
                var_type = "int"
            elif re.match(r'^\d+\.\d+$', var_val):
                var_type = "double"
            elif var_val.lower() in ['true', 'false']:
                var_type = "bool"
                var_val = var_val.lower()
            elif (var_val.startswith('"') or var_val.startswith("'")):
                var_type = "std::string"
            else:
                var_type = "auto" 
                
            cpp_body_statements.append(f"    {var_type} {var_name} = {var_val};")
            continue

        # C. Simple Control Flows Conversion
        if trimmed.startswith('if ') or trimmed.startswith('if('):
            condition = trimmed[2:-1].strip().rstrip(':')
            cpp_body_statements.append(f"    if ({condition}) {{")
            continue
        if trimmed.startswith('elif ') or trimmed.startswith('elif('):
            condition = trimmed[4:-1].strip().rstrip(':')
            cpp_body_statements.append(f"    }} else if ({condition}) {{")
            continue
        if trimmed.startswith('else:') or trimmed.rstrip(':') == 'else':
            cpp_body_statements.append("    } else {")
            continue

        # Universal statement processing fallback
        processed_statement = trimmed.replace(':', '')
        cpp_body_statements.append(f"    {processed_statement};")

    # Assemble final C++ draft structure cleanly
    cpp_blocks = ["#include <iostream>", "#include <string>", "", "int main() {"]
    for statement in cpp_body_statements:
        cpp_blocks.append(statement)
        
    # Balanced check closing
    open_brackets = "".join(cpp_blocks).count("{")
    close_brackets = "".join(cpp_blocks).count("}")
    while open_brackets > close_brackets:
        cpp_blocks.append("    }")
        close_brackets += 1
        
    cpp_blocks.append("    return 0;")
    cpp_blocks.append("}")
    
    final_cpp_code = "\n".join(cpp_blocks)

    # ==========================================
    # 🔬 CHECK 3: C++ SEMANTIC RE-VALIDATOR
    # ==========================================
    if "int main()" not in final_cpp_code:
        return {"status": "error", "message": "❌ Verification Failed: Structural error inside generated main()."}
    if final_cpp_code.count("{") != final_cpp_code.count("}"):
        return {"status": "error", "message": "❌ Verification Failed: Structural mismatch inside generated braces."}
    
    return {"status": "success", "cpp_code": final_cpp_code}

@app.route('/transpile', methods=['POST'])
def handle_api_request():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
            
        user_python_input = data.get("user_code", "")
        result = run_transpiler_engine(user_python_input)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
        
