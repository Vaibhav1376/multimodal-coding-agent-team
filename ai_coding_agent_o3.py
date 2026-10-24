"""
Enhanced AI Coding Agent with Multi-Agent Architecture
Features:
- Level 1: Self-Healing Loop (auto-fix errors)
- Level 2: Chat Memory & Context
- Level 3: File I/O Capabilities
- Level 4: Dynamic Dependencies
- Level 5: Multi-Agent Architecture (Architect, Developer, QA)
- Level 6: TDD Loop (Red-Green-Refactor)
- Level 7: Reflexion Pattern (pre-computation reasoning)
- Level 8: Linter Integration (ruff)
"""

from typing import Optional, Dict, Any, List, Tuple
import streamlit as st
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from agno.media import Image as AgnoImage
from e2b_code_interpreter import Sandbox
import os
import re
from PIL import Image
from io import BytesIO
import base64
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# CONSTANTS
# ============================================================================
MAX_SELF_HEALING_ATTEMPTS = 3
SUPPORTED_DATA_FILES = ['csv', 'txt', 'json', 'xlsx']

# Package mapping for common imports
PACKAGE_MAPPING = {
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'PIL': 'Pillow',
    'yaml': 'pyyaml',
    'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv',
}

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def initialize_session_state() -> None:
    """Initialize all session state variables."""
    defaults = {
        'openai_key': os.getenv('OPENAI_API_KEY', ''),
        'gemini_key': os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', ''),
        'e2b_key': os.getenv('E2B_API_KEY', ''),
        'sandbox': None,
        'messages': [],  # Chat history
        'uploaded_files': [],  # User uploaded data files
        'current_plan': '',  # Architect's plan
        'reflections': '',  # Thinking block
        'last_code': '',  # Last generated code
        'last_tests': '',  # Last generated tests
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ============================================================================
# SIDEBAR SETUP
# ============================================================================
def setup_sidebar() -> List[Any]:
    """Setup sidebar with API keys and file uploads."""
    uploaded_data_files = []
    
    with st.sidebar:
        st.title("🔧 Configuration")
        
        # API Keys Section
        with st.expander("🔑 API Keys", expanded=True):
            st.session_state.openai_key = st.text_input(
                "OpenAI API Key", 
                value=st.session_state.openai_key,
                type="password"
            )
            st.session_state.gemini_key = st.text_input(
                "Gemini API Key", 
                value=st.session_state.gemini_key,
                type="password"
            )
            st.session_state.e2b_key = st.text_input(
                "E2B API Key",
                value=st.session_state.e2b_key,
                type="password"
            )
        
        st.divider()
        
        # File Upload Section (Level 3)
        st.subheader("📁 Data Files")
        uploaded_data_files = st.file_uploader(
            "Upload files for analysis",
            type=SUPPORTED_DATA_FILES,
            accept_multiple_files=True,
            help="Upload CSV, TXT, JSON, or Excel files to analyze"
        )
        
        if uploaded_data_files:
            st.success(f"📎 {len(uploaded_data_files)} file(s) ready")
            for f in uploaded_data_files:
                st.caption(f"• {f.name}")
        
        st.divider()
        
        # Chat Controls
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.current_plan = ''
            st.session_state.reflections = ''
            st.session_state.last_code = ''
            st.session_state.last_tests = ''
            st.rerun()
        
        # Info
        st.info("⏱️ Execution timeout: 30s\n\n🔄 Max retry attempts: 3")
    
    return uploaded_data_files

# ============================================================================
# AGENT CREATION (Level 5: Multi-Agent Architecture)
# ============================================================================
def create_agents() -> Tuple[Agent, Agent, Agent, Agent, Agent]:
    """Create specialized agents for the Software House architecture."""
    
    # Use Gemini for all agents (fallback when OpenAI quota exceeded)
    gemini_model = "gemini-2.5-flash"
    
    # Vision Agent (Gemini) - For image processing
    vision_agent = Agent(
        model=Gemini(id="gemini-2.5-flash-lite", api_key=st.session_state.gemini_key),
        markdown=True,
    )
    
    # Architect Agent - Creates plans, no code
    architect_agent = Agent(
        model=Gemini(
            id=gemini_model,
            api_key=st.session_state.gemini_key,
        ),
        instructions="""You are the Architect Agent - a senior software architect.
            Your role is to ANALYZE problems and create TECHNICAL SPECIFICATIONS.
            
            You DO NOT write code. Instead, you:
            1. Analyze the problem requirements deeply
            2. Identify edge cases and constraints
            3. Design the solution architecture
            4. Specify class/function signatures with type hints
            5. Define test cases that should pass
            
            Output Format:
            ## Technical Specification
            ### Problem Analysis
            [Your analysis]
            
            ### Edge Cases
            - [List edge cases]
            
            ### Solution Design
            [Architecture description with function signatures]
            
            ### Test Cases
            [List of test assertions]
            """,
        markdown=True
    )
    
    # Developer Agent - Writes code based on architect's plan
    developer_agent = Agent(
        model=Gemini(
            id=gemini_model,
            api_key=st.session_state.gemini_key,
        ),
        instructions="""You are the Developer Agent - an expert Python programmer.
            You receive technical specifications from the Architect and implement them.
            
            Your code must:
            1. Follow the architect's design exactly
            2. Be clean, efficient, and well-documented
            3. Include proper type hints
            4. Handle all edge cases mentioned
            5. Be executable in an e2b sandbox
            
            When writing tests (TDD Red phase):
            - Write test functions using assert statements
            - Cover all specified test cases
            - Tests should FAIL initially (no implementation yet)
            
            When writing implementation (TDD Green phase):
            - Make all tests pass
            - Keep it simple - don't over-engineer
            """,
        markdown=True
    )
    
    # QA Agent - Tests, reviews, and refactors code
    qa_agent = Agent(
        model=Gemini(
            id=gemini_model,
            api_key=st.session_state.gemini_key,
        ),
        instructions="""You are the QA Agent - a quality assurance engineer.
            
            Your responsibilities:
            1. Review code for bugs and issues
            2. Suggest optimizations (time/space complexity)
            3. Ensure code follows best practices
            4. Validate that all tests pass
            5. Suggest refactoring improvements
            
            When reviewing:
            - Check for potential runtime errors
            - Verify edge case handling
            - Assess code readability
            - Suggest performance improvements
            """,
        markdown=True
    )
    
    # Execution Agent - Runs and explains results
    execution_agent = Agent(
        model=Gemini(
            id=gemini_model,
            api_key=st.session_state.gemini_key,
        ),
        instructions="""You are the Execution Agent.
            Your task is to:
            1. Execute Python code in the sandbox
            2. Analyze and format results clearly
            3. Explain any errors encountered
            4. Provide actionable feedback
            """,
        markdown=True
    )
    
    return vision_agent, architect_agent, developer_agent, qa_agent, execution_agent


# ============================================================================
# SANDBOX MANAGEMENT
# ============================================================================
def initialize_sandbox() -> None:
    """Initialize or reinitialize the E2B sandbox."""
    try:
        if st.session_state.sandbox:
            try:
                st.session_state.sandbox.kill()
            except:
                pass
        os.environ['E2B_API_KEY'] = st.session_state.e2b_key
        st.session_state.sandbox = Sandbox.create()
    except Exception as e:
        st.error(f"Failed to initialize sandbox: {str(e)}")
        st.session_state.sandbox = None

def upload_files_to_sandbox(sandbox: Sandbox, files: List[Any]) -> List[str]:
    """Upload user files to sandbox (Level 3)."""
    uploaded_paths = []
    for file in files:
        try:
            content = file.read()
            file_path = f"/home/user/{file.name}"
            sandbox.files.write(file_path, content)
            uploaded_paths.append(file_path)
            file.seek(0)  # Reset file pointer
        except Exception as e:
            st.warning(f"Failed to upload {file.name}: {str(e)}")
    return uploaded_paths

# ============================================================================
# DYNAMIC DEPENDENCIES (Level 4)
# ============================================================================
def extract_imports(code: str) -> List[str]:
    """Extract import statements from code."""
    imports = set()
    
    # Match: import xxx, from xxx import yyy
    import_patterns = [
        r'^import\s+([\w]+)',
        r'^from\s+([\w]+)',
    ]
    
    for line in code.split('\n'):
        line = line.strip()
        for pattern in import_patterns:
            match = re.match(pattern, line)
            if match:
                module = match.group(1)
                # Skip standard library modules
                stdlib = {'os', 'sys', 're', 'json', 'math', 'random', 'time', 
                         'datetime', 'collections', 'itertools', 'functools',
                         'typing', 'pathlib', 'io', 'string', 'copy', 'operator'}
                if module not in stdlib:
                    imports.add(module)
    
    return list(imports)

def get_pip_packages(modules: List[str]) -> List[str]:
    """Convert module names to pip package names."""
    packages = []
    for module in modules:
        # Check if there's a mapping
        pip_name = PACKAGE_MAPPING.get(module, module)
        packages.append(pip_name)
    return packages

def install_dependencies(sandbox: Sandbox, packages: List[str]) -> bool:
    """Install required packages in sandbox."""
    if not packages:
        return True
    
    try:
        pip_cmd = f"pip install -q {' '.join(packages)}"
        result = sandbox.run_code(pip_cmd)
        return result.error is None
    except Exception as e:
        st.warning(f"Failed to install packages: {str(e)}")
        return False

# ============================================================================
# LINTER INTEGRATION (Level 8)
# ============================================================================
def setup_linter(sandbox: Sandbox) -> bool:
    """Install ruff linter in sandbox."""
    try:
        sandbox.run_code("pip install -q ruff")
        return True
    except:
        return False

def run_linter(sandbox: Sandbox, code: str) -> Tuple[str, str]:
    """Run ruff linter and return issues and fixed code."""
    try:
        # Write code to file
        sandbox.files.write("/home/user/solution.py", code)
        
        # Check for issues
        check_result = sandbox.run_code("ruff check /home/user/solution.py 2>&1 || true")
        issues = check_result.logs.stdout if check_result.logs else ""
        
        # Auto-fix
        sandbox.run_code("ruff check --fix /home/user/solution.py 2>&1 || true")
        
        # Read fixed code
        try:
            fixed_code = sandbox.files.read("/home/user/solution.py")
            if isinstance(fixed_code, bytes):
                fixed_code = fixed_code.decode('utf-8')
        except:
            fixed_code = code
        
        return issues, fixed_code
    except Exception as e:
        return f"Linter error: {str(e)}", code

# ============================================================================
# REFLEXION PATTERN (Level 7)
# ============================================================================
def generate_reflection(agent: Agent, problem: str) -> str:
    """Generate pre-computation reasoning."""
    prompt = f"""Before solving this problem, think through it carefully.

Problem: {problem}

Please provide your analysis in this format:

<thinking>
## Edge Cases
- What if the input is empty?
- What are the boundary conditions?

## Constraints
- Time complexity requirements?
- Space complexity limits?
- Input size limits?

## Assumptions
- What input validation is needed?
- What can we assume about the input?

## Approach
- What algorithm/data structure fits best?
- Why this approach over alternatives?
</thinking>
"""
    response: RunOutput = agent.run(prompt)
    return response.content

# ============================================================================
# TDD LOOP (Level 6)
# ============================================================================
def generate_tests(developer_agent: Agent, plan: str, problem: str) -> str:
    """Generate test file (TDD Red phase)."""
    prompt = f"""Based on the architect's plan, write test cases FIRST.

## Architect's Plan
{plan}

## Original Problem
{problem}

Write a complete test file with:
1. Import statements (if needed)
2. Test functions using assert statements
3. Edge case tests
4. At least 3-5 test cases

Output ONLY the Python test code in a code block.
"""
    response: RunOutput = developer_agent.run(prompt)
    return response.content

def generate_solution(developer_agent: Agent, plan: str, tests: str, problem: str) -> str:
    """Generate solution code (TDD Green phase)."""
    prompt = f"""Implement the solution to make all tests pass.

## Architect's Plan
{plan}

## Test Cases to Pass
{tests}

## Original Problem
{problem}

Write clean, efficient code that passes ALL tests.
Output ONLY the Python solution code in a code block.
"""
    response: RunOutput = developer_agent.run(prompt)
    return response.content

# ============================================================================
# SELF-HEALING LOOP (Level 1)
# ============================================================================
def self_healing_execute(
    sandbox: Sandbox,
    code: str,
    developer_agent: Agent,
    execution_agent: Agent,
    tests: str = "",
    max_attempts: int = MAX_SELF_HEALING_ATTEMPTS
) -> Tuple[str, str, bool]:
    """Execute code with automatic error recovery."""
    
    current_code = code
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        
        try:
            # If we have tests, run them first
            if tests:
                # Write both files
                sandbox.files.write("/home/user/solution.py", current_code)
                sandbox.files.write("/home/user/test_solution.py", tests)
                
                # Run tests with timeout
                execution = sandbox.run_code("""
import sys
sys.path.insert(0, '/home/user')
exec(open('/home/user/solution.py').read())
exec(open('/home/user/test_solution.py').read())
print("✅ All tests passed!")
""", timeout=30)
            else:
                execution = sandbox.run_code(current_code, timeout=30)
            
            # Check for errors
            if execution.error:
                error_msg = str(execution.error)
                
                # Timeout handling
                if "TimeoutException" in error_msg:
                    return "⚠️ Execution Timeout: Code took >30 seconds.", current_code, False
                
                # Self-healing: Ask developer to fix
                if attempt < max_attempts:
                    st.warning(f"🔄 Attempt {attempt}/{max_attempts} failed. Self-healing...")
                    
                    fix_prompt = f"""The code execution resulted in an error.

## Error Message
{error_msg}

## Original Code
```python
{current_code}
```

Please analyze the error and provide a FIXED version of the code.
Output ONLY the corrected Python code in a code block.
"""
                    fix_response: RunOutput = developer_agent.run(fix_prompt)
                    
                    # Extract fixed code
                    fixed_code = extract_code_block(fix_response.content)
                    if fixed_code:
                        current_code = fixed_code
                        continue
                
                # Final failure
                error_prompt = f"Analyze this error and explain what went wrong:\n{error_msg}"
                error_response: RunOutput = execution_agent.run(error_prompt)
                return f"⚠️ Execution Error (after {attempt} attempts):\n{error_response.content}", current_code, False
            
            # Success!
            logs = ""
            if execution.logs:
                logs = execution.logs.stdout or ""
                if execution.logs.stderr:
                    logs += f"\nStderr: {execution.logs.stderr}"
            
            return f"✅ Execution successful (attempt {attempt}):\n```\n{logs}\n```", current_code, True
            
        except Exception as e:
            if attempt >= max_attempts:
                return f"⚠️ Sandbox Error: {str(e)}", current_code, False
            initialize_sandbox()
    
    return "⚠️ Max attempts reached.", current_code, False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def extract_code_block(text: str) -> str:
    """Extract Python code from markdown code block."""
    if "```python" in text:
        parts = text.split("```python")
        if len(parts) > 1:
            return parts[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) > 1:
            return parts[1].strip()
    return text.strip()

def process_image_with_gemini(vision_agent: Agent, image: Image) -> str:
    """Extract coding problem from image using Gemini."""
    prompt = """Analyze this image and extract any coding problem or code snippet shown. 
    Describe it in clear natural language, including any:
    1. Problem statement
    2. Input/output examples
    3. Constraints or requirements
    Format it as a proper coding problem description."""
    
    temp_path = "temp_image.png"
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(temp_path, format="PNG")
        
        agno_image = AgnoImage(filepath=Path(temp_path))
        response: RunOutput = vision_agent.run(prompt, images=[agno_image])
        return response.content
    except Exception as e:
        return f"Failed to process image: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def display_chat_history():
    """Display conversation history (Level 2)."""
    if st.session_state.messages:
        with st.expander("💬 Conversation History", expanded=False):
            for i, msg in enumerate(st.session_state.messages):
                role_icon = "👤" if msg["role"] == "user" else "🤖"
                st.markdown(f"**{role_icon} {msg['role'].title()}:**")
                st.markdown(msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"])
                if msg.get("code"):
                    with st.expander("View Code"):
                        st.code(msg["code"], language="python")
                st.divider()

def add_to_history(role: str, content: str, code: str = ""):
    """Add message to conversation history."""
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "code": code
    })

def get_context_prompt() -> str:
    """Build context from conversation history."""
    if not st.session_state.messages:
        return ""
    
    context = "\n## Previous Conversation Context:\n"
    for msg in st.session_state.messages[-5:]:  # Last 5 messages
        context += f"\n{msg['role'].upper()}: {msg['content'][:300]}"
        if msg.get("code"):
            context += f"\n```python\n{msg['code'][:500]}\n```"
    return context

# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main() -> None:
    st.set_page_config(
        page_title="AI Coding Agent",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 Semi-Autonomous AI Coding Agent")
    st.caption("Powered by Multi-Agent Architecture with Self-Healing & TDD")
    
    initialize_session_state()
    uploaded_data_files = setup_sidebar()
    
    # Check API keys
    if not (st.session_state.openai_key and 
            st.session_state.gemini_key and 
            st.session_state.e2b_key):
        st.warning("⚠️ Please enter all required API keys in the sidebar.")
        return
    
    # Create agents
    vision_agent, architect_agent, developer_agent, qa_agent, execution_agent = create_agents()
    
    # Display chat history (Level 2)
    display_chat_history()
    
    # Input Section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_image = st.file_uploader(
            "📷 Upload problem image (optional)",
            type=['png', 'jpg', 'jpeg']
        )
        
        if uploaded_image:
            st.image(uploaded_image, caption="Uploaded Image", width=400)
    
    with col2:
        # Show uploaded data files info
        if uploaded_data_files:
            st.info(f"📊 Data files ready: {', '.join([f.name for f in uploaded_data_files])}")
    
    user_query = st.text_area(
        "💡 Describe your coding problem or follow-up request:",
        placeholder="Example: Write a function to find the longest palindromic substring.\n\nOr follow-up: Can you optimize the previous solution?",
        height=100
    )
    
    # Advanced Options
    with st.expander("⚙️ Advanced Options"):
        enable_tdd = st.checkbox("Enable TDD Mode (Test-Driven Development)", value=True)
        enable_reflection = st.checkbox("Enable Reflexion (Pre-computation Reasoning)", value=True)
        enable_linting = st.checkbox("Enable Linter (Code Quality Check)", value=True)
    
    # Process Button
    if st.button("🚀 Generate & Execute Solution", type="primary", use_container_width=True):
        
        # Validate input
        if uploaded_image and user_query:
            st.error("Please use either image upload OR text input, not both.")
            return
        if not uploaded_image and not user_query:
            st.warning("Please provide an image or text description.")
            return
        
        # Initialize sandbox
        initialize_sandbox()
        if not st.session_state.sandbox:
            st.error("Failed to initialize sandbox. Check E2B API key.")
            return
        
        # Upload data files to sandbox (Level 3)
        file_context = ""
        if uploaded_data_files:
            with st.spinner("📤 Uploading data files to sandbox..."):
                uploaded_paths = upload_files_to_sandbox(st.session_state.sandbox, uploaded_data_files)
                if uploaded_paths:
                    file_context = f"\n\n📁 Available files in sandbox: {', '.join(uploaded_paths)}"
                    st.success(f"Uploaded {len(uploaded_paths)} files to sandbox")
        
        # Get problem statement
        problem = ""
        if uploaded_image:
            with st.spinner("🔍 Processing image..."):
                image = Image.open(uploaded_image)
                problem = process_image_with_gemini(vision_agent, image)
                if problem.startswith("Failed"):
                    st.error(problem)
                    return
                st.info("📝 Extracted Problem:")
                st.write(problem)
        else:
            problem = user_query
        
        # Add conversation context (Level 2)
        context = get_context_prompt()
        full_problem = problem + context + file_context
        
        # Add user message to history
        add_to_history("user", problem)
        
        # ============================================================
        # STEP 1: Reflexion - Pre-computation Reasoning (Level 7)
        # ============================================================
        if enable_reflection:
            with st.spinner("🧠 Analyzing problem (Reflexion)..."):
                reflection = generate_reflection(architect_agent, full_problem)
                st.session_state.reflections = reflection
                
                with st.expander("🧠 Pre-computation Reasoning", expanded=True):
                    st.markdown(reflection)
        
        # ============================================================
        # STEP 2: Architect creates plan (Level 5)
        # ============================================================
        with st.spinner("📐 Architect Agent creating technical specification..."):
            plan_prompt = f"""Create a technical specification for this problem.

{full_problem}

{st.session_state.reflections if enable_reflection else ''}
"""
            plan_response: RunOutput = architect_agent.run(plan_prompt)
            plan = plan_response.content
            st.session_state.current_plan = plan
            
            with st.expander("📐 Technical Specification", expanded=True):
                st.markdown(plan)
        
        # ============================================================
        # STEP 3: TDD Loop (Level 6)
        # ============================================================
        tests = ""
        if enable_tdd:
            # RED: Generate tests first
            with st.spinner("🔴 Developer Agent writing tests (TDD Red)..."):
                tests_response = generate_tests(developer_agent, plan, full_problem)
                tests = extract_code_block(tests_response)
                st.session_state.last_tests = tests
                
                with st.expander("🔴 Test Cases (TDD Red)", expanded=False):
                    st.code(tests, language="python")
        
        # GREEN: Generate solution
        with st.spinner("🟢 Developer Agent implementing solution..."):
            if enable_tdd:
                solution_response = generate_solution(developer_agent, plan, tests, full_problem)
            else:
                dev_prompt = f"""Implement a solution based on the architect's plan.

{plan}

Problem: {full_problem}

Output clean, efficient Python code.
"""
                solution_response: RunOutput = developer_agent.run(dev_prompt)
                solution_response = solution_response.content
            
            code = extract_code_block(solution_response if isinstance(solution_response, str) else solution_response)
            st.session_state.last_code = code
        
        # Display solution
        st.divider()
        st.subheader("💻 Solution")
        st.code(code, language="python")
        
        # ============================================================
        # STEP 4: Install Dependencies (Level 4)
        # ============================================================
        with st.spinner("📦 Checking dependencies..."):
            imports = extract_imports(code)
            if tests:
                imports.extend(extract_imports(tests))
            imports = list(set(imports))
            
            if imports:
                packages = get_pip_packages(imports)
                st.info(f"📦 Installing: {', '.join(packages)}")
                install_dependencies(st.session_state.sandbox, packages)
        
        # ============================================================
        # STEP 5: Linter Check (Level 8)
        # ============================================================
        if enable_linting:
            with st.spinner("🔍 Running linter..."):
                setup_linter(st.session_state.sandbox)
                lint_issues, fixed_code = run_linter(st.session_state.sandbox, code)
                
                if lint_issues and "error" not in lint_issues.lower():
                    with st.expander("🔍 Linter Report"):
                        st.text(lint_issues if lint_issues else "No issues found!")
                
                if fixed_code != code:
                    code = fixed_code
                    st.session_state.last_code = code
                    with st.expander("✨ Auto-formatted Code"):
                        st.code(code, language="python")
        
        # ============================================================
        # STEP 6: Execute with Self-Healing (Level 1)
        # ============================================================
        with st.spinner("🚀 Executing code (with self-healing)..."):
            result, final_code, success = self_healing_execute(
                st.session_state.sandbox,
                code,
                developer_agent,
                execution_agent,
                tests if enable_tdd else ""
            )
            
            # Update if code was fixed
            if final_code != code:
                st.session_state.last_code = final_code
                st.info("🔄 Code was automatically fixed during execution")
                with st.expander("🔧 Final Code (after fixes)"):
                    st.code(final_code, language="python")
        
        # Display results
        st.divider()
        st.subheader("🚀 Execution Results")
        if success:
            st.success("Execution completed successfully!")
        st.markdown(result)
        
        # ============================================================
        # STEP 7: QA Review (Level 5)
        # ============================================================
        if success:
            with st.spinner("🔬 QA Agent reviewing code..."):
                qa_prompt = f"""Review this code for quality and suggest improvements.

```python
{final_code}
```

Execution Result: {result[:500]}

Provide:
1. Code quality assessment
2. Potential optimizations
3. Any remaining issues
"""
                qa_response: RunOutput = qa_agent.run(qa_prompt)
                
                with st.expander("🔬 QA Review", expanded=False):
                    st.markdown(qa_response.content)
        
        # Add assistant response to history
        add_to_history("assistant", result, final_code)
        
        # Show generated files
        try:
            files = st.session_state.sandbox.files.list("/home/user")
            if files:
                with st.expander("📁 Generated Files"):
                    st.json([str(f) for f in files])
        except:
            pass

if __name__ == "__main__":
    main()