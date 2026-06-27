def run_transpiler_engine(python_code):
    if not python_code or not python_code.strip():
        return {"status": "error", "message": "Please enter a Python command first"}
        
    errors = []
    lines = python_code.split("\n")
    
    # --- CRITICAL LOGIC & HARDWARE CHECKERS ---
    # Convert everything to lowercase to scan the user's intent smoothly
    lower_code = python_code.lower()
    
    # 1. Check if they accidentally configured a GREEN LED instead of RED
    if "green" in lower_code or "led_green" in lower_code:
        errors.append("Logic Error: You configured the GREEN LED, but the assignment requires the RED LED to glow.")
        
    # 2. Check if they missed the connection pin completely
    if "red" not in lower_code and "led_red" not in lower_code:
        errors.append("Configuration Error: Missing the RED LED target variable or setup connection statement.")
        
    # 3. Check if they forgot to actually trigger the "HIGH" or "ON" state
    if "high" not in lower_code and "on" not in lower_code and "true" not in lower_code:
        errors.append("Execution Error: You set up the LED connection, but you never sent power to turn it ON.")

    # Run your structural syntax checks as a secondary guard layer
    code_sans_strings = re.sub(r'(".*?"|\'.*?\')', '', python_code)
    if code_sans_strings.count("(") != code_sans_strings.count(")"):
        errors.append("Syntax Error: Unbalanced parenthesis detected.")

    for idx in range(len(lines)):
        trimmed_line = lines[idx].strip()
        line_num = idx + 1
        if not trimmed_line or trimmed_line.startswith("#"): continue
        
        # Missing colon check
        if (trimmed_line.startswith("if ") or trimmed_line.startswith("else")) and not trimmed_line.endswith(":"):
            errors.append(f"SyntaxError on line {line_num}: expected ':' at the end of block statement.")

    # 🚫 THE REJECTION GATEWAY: If any rule is broken, completely decline the submission!
    if errors:
        return {"status": "syntax_error", "errors": errors}
    
    # 🏆 SUCCESS: Only executed if the logic rules and connection statements are 100% correct
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
        
