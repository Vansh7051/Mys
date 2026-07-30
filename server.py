import ast
import os
import re
from typing import List, Set, Dict
from flask import Flask, request, jsonify

app = Flask(__name__)

class CppASTTranspiler(ast.NodeVisitor):
    """
    Advanced AST Visitor that walks Python code AST and transpiles it into
    valid, statically typed Arduino C++ code.
    """
    def __init__(self):
        self.includes: Set[str] = {"Arduino.h"}
        self.global_vars: Dict[str, str] = {}  # var_name -> C++ type
        self.pin_outputs: Set[str] = set()
        self.pin_inputs: Set[str] = set()
        self.setup_code: List[str] = []
        self.loop_code: List[str] = []
        self.functions: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name
            if name in ["time", "utime"]:
                pass  # Mapped to native delay() / delayMicroseconds()
            elif name in ["machine", "driver"]:
                pass  # Mapped to native Arduino GPIO
            else:
                # Dynamically convert python import module to C++ header
                self.includes.add(f"{name}.h")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            if node.module not in ["time", "utime", "machine"]:
                self.includes.add(f"{node.module}.h")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Handles pin definitions like: led = Pin(5, Pin.OUT) or value assignments
        var_name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else "var"
        
        # Check if right-hand side is Pin instantiation
        if isinstance(node.value, ast.Call):
            func_name = self._get_full_func_name(node.value.func)
            if "Pin" in func_name:
                pin_num = self.visit(node.value.args[0])
                mode = "OUTPUT"
                if len(node.value.args) > 1:
                    mode_str = ast.dump(node.value.args[1])
                    if "IN" in mode_str:
                        mode = "INPUT"

                self.global_vars[var_name] = "int"
                self.setup_code.append(f"  {var_name} = {pin_num};")
                if mode == "OUTPUT":
                    self.pin_outputs.add(var_name)
                    self.setup_code.append(f"  pinMode({var_name}, OUTPUT);")
                else:
                    self.pin_inputs.add(var_name)
                    self.setup_code.append(f"  pinMode({var_name}, INPUT);")
                return

        # General variable assignments
        cpp_val = self.visit(node.value)
        inferred_type = "int"
        if isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, float):
                inferred_type = "float"
            elif isinstance(node.value.value, str):
                inferred_type = "String"
            elif isinstance(node.value.value, bool):
                inferred_type = "bool"

        if var_name not in self.global_vars:
            self.global_vars[var_name] = inferred_type
            return f"  {inferred_type} {var_name} = {cpp_val};"
        else:
            return f"  {var_name} = {cpp_val};"

    def visit_Call(self, node: ast.Call) -> str:
        func_name = self._get_full_func_name(node.func)
        args = [self.visit(arg) for arg in node.args]

        # 1. Delay conversions
        if func_name in ["time.sleep", "utime.sleep", "sleep"]:
            # If argument is float seconds, convert to milliseconds
            sec = args[0] if args else "1"
            try:
                ms = int(float(sec) * 1000)
                return f"delay({ms});"
            except ValueError:
                return f"delay((unsigned long)(({sec}) * 1000));"

        elif func_name in ["time.sleep_ms", "utime.sleep_ms", "delay"]:
            return f"delay({args[0] if args else '1000'});"

        # 2. GPIO methods: pin.value(1) or pin.on() / pin.off()
        elif ".value" in func_name or ".on" in func_name or ".off" in func_name:
            obj_name = func_name.split(".")[0]
            if ".on" in func_name:
                val = "HIGH"
            elif ".off" in func_name:
                val = "LOW"
            else:
                val = "HIGH" if args and args[0] in ["1", "True"] else "LOW"
            return f"digitalWrite({obj_name}, {val});"

        # 3. Print statements to Serial
        elif func_name == "print":
            self.setup_code.append("  Serial.begin(115200);")
            return f'Serial.println({", ".join(args)});'

        # Default fallback: Direct function call
        return f"{func_name}({', '.join(args)});"

    def visit_If(self, node: ast.If) -> str:
        test = self.visit(node.test)
        body = "\n".join([self.visit(stmt) for stmt in node.body if self.visit(stmt)])
        orelse = ""
        if node.orelse:
            else_body = "\n".join([self.visit(stmt) for stmt in node.orelse if self.visit(stmt)])
            orelse = f" else {{\n{else_body}\n}}"
        return f"  if ({test}) {{\n{body}\n}}{orelse}"

    def visit_For(self, node: ast.For) -> str:
        # Handles for i in range(x)
        var = node.target.id if isinstance(node.target, ast.Name) else "i"
        limit = "10"
        if isinstance(node.iter, ast.Call) and getattr(node.iter.func, 'id', '') == 'range':
            limit = self.visit(node.iter.args[0])
        
        body = "\n".join([self.visit(stmt) for stmt in node.body if self.visit(stmt)])
        return f"  for (int {var} = 0; {var} < {limit}; {var}++) {{\n{body}\n  }}"

    def visit_While(self, node: ast.While) -> str:
        test = self.visit(node.test)
        body = "\n".join([self.visit(stmt) for stmt in node.body if self.visit(stmt)])
        return f"  while ({test}) {{\n{body}\n  }}"

    def visit_BinOp(self, node: ast.BinOp) -> str:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_map = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.Mod: "%", ast.BitAnd: "&", ast.BitOr: "|"
        }
        op = op_map.get(type(node.op), "+")
        return f"({left} {op} {right})"

    def visit_Compare(self, node: ast.Compare) -> str:
        left = self.visit(node.left)
        comparators = [self.visit(c) for c in node.comparators]
        op_map = {
            ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<",
            ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="
        }
        op = op_map.get(type(node.ops[0]), "==")
        return f"{left} {op} {comparators[0]}"

    def visit_Constant(self, node: ast.Constant) -> str:
        if isinstance(node.value, str):
            return f'"{node.value}"'
        elif isinstance(node.value, bool):
            return "true" if node.value else "false"
        return str(node.value)

    def visit_Name(self, node: ast.Name) -> str:
        return node.id

    def visit_Expr(self, node: ast.Expr):
        res = self.visit(node.value)
        return f"  {res}" if res and not res.endswith(";") else res

    def _get_full_func_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_full_func_name(node.value)}.{node.attr}"
        return "unknown"


def transpile_python_to_cpp(py_code: str) -> str:
    """Entry point for parsing Python and emitting structured Arduino C++ code."""
    if not py_code.strip():
        return "#include <Arduino.h>\n\nvoid setup() {}\nvoid loop() {}\n"

    try:
        tree = ast.parse(py_code)
    except SyntaxError as e:
        return f"// Transpilation Error: Invalid Python Syntax\n// {str(e)}"

    transpiler = CppASTTranspiler()
    statements = []

    for stmt in tree.body:
        res = transpiler.visit(stmt)
        if res:
            statements.append(res)

    # Reconstruct standard C++ structure
    cpp_out = []
    
    # 1. Includes
    for inc in sorted(transpiler.includes):
        cpp_out.append(f"#include <{inc}>")
    cpp_out.append("")

    # 2. Global variables
    for var, vtype in transpiler.global_vars.items():
        cpp_out.append(f"{vtype} {var};")
    cpp_out.append("")

    # 3. void setup()
    cpp_out.append("void setup() {")
    # Deduplicate setup routines
    seen_setup = set()
    for s in transpiler.setup_code:
        if s not in seen_setup:
            cpp_out.append(s)
            seen_setup.add(s)
    cpp_out.append("}")
    cpp_out.append("")

    # 4. void loop()
    cpp_out.append("void loop() {")
    for stmt in statements:
        if stmt and not stmt.startswith("#include"):
            cpp_out.append(stmt if stmt.endswith(";") or stmt.endswith("}") else f"{stmt};")
    cpp_out.append("}")

    return "\n".join(cpp_out)


@app.route("/transpile", methods=["POST"])
def transpile():
    data = request.get_json(force=True, silent=True) or {}
    raw_code = data.get("code", "")
    cpp_result = transpile_python_to_cpp(raw_code)
    return jsonify({"status": "success", "result": cpp_result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
    
