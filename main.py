from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import io
import pypdf
import docx
from lessons import LESSON_LIBRARY

app = FastAPI(title="AI Career Platform - AI Service")

import os
from dotenv import load_dotenv
from groq import Groq
import json
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Groq Configuration (Primary & Secondary)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY_SECONDARY = os.getenv("GROQ_API_KEY_SECONDARY")

if not GROQ_API_KEY:
    logger.warning("WARNING: GROQ_API_KEY not found in environment.")
    client_primary = None
else:
    client_primary = Groq(api_key=GROQ_API_KEY)
    logger.info("Primary Groq AI successfully initialized.")

if not GROQ_API_KEY_SECONDARY:
    logger.warning("WARNING: GROQ_API_KEY_SECONDARY not found in environment.")
    client_secondary = None
else:
    client_secondary = Groq(api_key=GROQ_API_KEY_SECONDARY)
    logger.info("Secondary Groq AI successfully initialized.")

# AI Model Configuration
AI_MODEL = "llama-3.3-70b-versatile"

def get_active_client():
    return client_primary or client_secondary

async def generate_groq_response_with_fallback(messages, stream=False):
    """Wrapper to handle dual Groq API keys with fallback logic."""
    if not get_active_client():
        raise Exception("No Groq API clients are configured.")
        
    try:
        if client_primary:
            return client_primary.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                stream=stream
            )
    except Exception as e:
        logger.error(f"Primary Groq API failed: {str(e)}")
        if client_secondary:
            logger.info("Attempting Fallback with Secondary Groq API Key...")
            return client_secondary.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                stream=stream
            )
        raise e
    
    if client_secondary:
         return client_secondary.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                stream=stream
            )
    raise Exception("Groq API client failed or missing.")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    domain: str
    topic: str = "General"

class InterviewChatRequest(BaseModel):
    message: str
    role: str # e.g., "Software Engineer"
    resume_context: str
    transcript: list # the history of the conversation

class EvalRequest(BaseModel):
    domain: str
    transcript: list
    role: str = ""

class RoadmapRequest(BaseModel):
    domain: str

class RecommendDomainRequest(BaseModel):
    education: str
    experience: str
    skills: list
    available_domains: list

class LessonRequest(BaseModel):
    domain: str
    topic: str
    difficulty: str = "Beginner"

class AnalyzeResumeRequest(BaseModel):
    resume_text: str
    target_role: str = "Software Engineer"

class CodingQuestionAnswer(BaseModel):
    questionText: str
    userAnswer: str

class ExamCodingEvalRequest(BaseModel):
    domain: str
    answers: list[CodingQuestionAnswer]
    language: str = "javascript"

class BoilerplateRequest(BaseModel):
    title: str
    description: str

class TestCaseRequest(BaseModel):
    title: str
    description: str

class TestCaseRequest(BaseModel):
    title: str
    description: str

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "DevElevate AI Service",
        "models": {
            "primary": f"Groq ({AI_MODEL})" if client_primary else "Not configured",
            "secondary": f"Groq Fallback ({AI_MODEL})" if client_secondary else "Not configured",
        }
    }

@app.post("/parse_resume")
async def parse_resume(file: UploadFile = File(...)):
    name = file.filename.lower()
    content = await file.read()
    text = ""
    
    try:
        if name.endswith(".pdf"):
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            # Try to read as plain text for other formats
            try:
                text = content.decode('utf-8')
            except:
                raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOCX or TXT.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
    
    return {"text": text.strip()}

@app.post("/analyze_resume")
async def analyze_resume(request: AnalyzeResumeRequest):
    logger.info(f"Analyzing resume for role: {request.target_role}")
    
    system_prompt = (
        "You are a highly critical and realistic ATS (Applicant Tracking System) and Senior Tech Recruiter. "
        "Your task is to provide an honest, data-driven analysis of a resume for a specific target role. "
        "A standard okay resume should score 60-70. A poor match should score below 50. A 90+ score is for perfect candidates. "
        "Be HARSH but ACTIONABLE. Mention specific missing technologies or weak descriptions."
    )
    
    user_prompt = f"""
    Analyze the following resume for the target role of '{request.target_role}'.
    
    RESUME TEXT:
    {request.resume_text}
    
    Provide a comprehensive analysis. Return ONLY a valid JSON object with:
    1. 'score': Integer (0-100).
    2. 'improvements': List of 3-5 specific points (referencing content in the resume).
    3. 'generatedQuestions': List of 3 tough interview questions tailored to the resume.
    
    Return ONLY raw JSON, no markdown.
    """

    # Try Groq with Fallback
    try:
        completion = await generate_groq_response_with_fallback(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        logger.info(f"Groq Response: {raw_text[:100]}...")
        return parse_json_safely(raw_text)
    except Exception as e:
        logger.error(f"Groq generation failed: {str(e)}")

    # Final Fallback on failure
    return {
        "score": 0,
        "improvements": ["AI Analysis currently unavailable. Please check your API keys limit."],
        "generatedQuestions": ["Unable to generate questions."]
    }

def parse_json_safely(text):
    try:
        # Clean potential markdown
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON Parse error: {str(e)}")
        raise ValueError("Invalid JSON response from AI")

@app.post("/interview_chat")
async def interview_chat(request: InterviewChatRequest):
    if not get_active_client():
        raise HTTPException(status_code=503, detail="Groq AI service is not configured.")
    # Build a professional system prompt
    messages = [
        {"role": "system", "content": (
            "You are a Senior Technical Interviewer from a Tier-1 Tech Company. Your tone is professional, observant, and encouraging yet rigorous. "
            f"You are conducting a formal interview for the position of: {request.role}.\n"
            f"CONTEXT - Candidate Resume Highlights:\n{request.resume_context}\n\n"
            "### CONVERSATION RULES:\n"
            "1. Stay in character as a professional interviewer. Do NOT mention you are an AI.\n"
            "2. Analyze the candidate's last response and ask exactly ONE insightful follow-up question.\n"
            "3. Focus on technical depth, problem-solving, and cultural fit.\n"
            "4. If the candidate asks about the company, answer professionally based on standard tech industry culture."
        )}
    ]
    
    for entry in request.transcript:
        role = "user" if entry['role'] == 'user' else "assistant"
        messages.append({"role": role, "content": entry['text']})
    
    async def generate():
        try:
            completion = await generate_groq_response_with_fallback(
                messages=messages,
                stream=True
            )
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    messages = [
        {"role": "system", "content": (
            f"You are an expert AI teacher specializing in {request.domain}. "
            f"The student is currently learning the topic: '{request.topic}'. "
            "Provide a helpful, concise, and technically accurate response to their query."
        )},
        {"role": "user", "content": request.message}
    ]
    
    async def generate():
        try:
            completion = await generate_groq_response_with_fallback(
                messages=messages,
                stream=True
            )
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error connecting to AI service: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/evaluate_exam_coding")
async def evaluate_exam_coding(req: ExamCodingEvalRequest):
    results = []
    
    for ans in req.answers:
        messages = [
            {"role": "system", "content": f"You are an extremely strict Senior Software Engineer code reviewer. Your expertise is in {req.domain} and {req.language}."},
            {"role": "user", "content": (
                f"Critically evaluate the following user answer for the question: '{ans.questionText}'\n\n"
                f"### EXPECTED LANGUAGE:\n{req.language}\n\n"
                f"### USER ANSWER:\n{ans.userAnswer}\n\n"
                "### EVALUATION RULES (CRITICAL):\n"
                "1. **Language Mismatch**: If the code is clearly NOT written in the expected language (e.g. Java syntax when JS is expected), you MUST fail it immediately (score 0, isCorrect false).\n"
                "2. **Correctness**: The code must solve the problem correctly. If it has syntax errors, logical errors, or produces incorrect output for edge cases, fail it.\n"
                "3. **Completeness**: If the user submits random text, empty functions, or just boilerplate without logic, fail it.\n\n"
                "Provide a strict evaluation. Return ONLY a valid JSON object with EXACTLY these keys:\n"
                " - 'score' (integer 0-10, strictly graded. 10 is perfect, <7 is failing).\n"
                " - 'feedback' (concise 1-2 sentence explanation of what is wrong or right. If language mismatch, say so).\n"
                " - 'isCorrect' (boolean. True ONLY if the logic is flawless AND the language matches).\n"
                "Do NOT wrap the JSON in markdown blocks like ```json."
            )}
        ]
        
        try:
            completion = await generate_groq_response_with_fallback(
                messages=messages,
                stream=False
            )
            raw_text = completion.choices[0].message.content.strip()
            import re
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            eval_data = json.loads(match.group(0)) if match else json.loads(raw_text)
            
            results.append({
                "questionText": ans.questionText,
                "userAnswer": ans.userAnswer,
                "aiFeedback": eval_data.get("feedback", "No feedback provided."),
                "score": eval_data.get("score", 0),
                "isCorrect": eval_data.get("isCorrect", False)
            })
        except Exception as e:
            results.append({
                "questionText": ans.questionText,
                "userAnswer": ans.userAnswer,
                "aiFeedback": f"Evaluation error: {str(e)}",
                "score": 0,
                "isCorrect": False
            })
            
    return {"results": results}

@app.post("/generate_boilerplates")
async def generate_boilerplates(req: BoilerplateRequest):
    logger.info(f"Generating boilerplates for: {req.title}")
    
    system_prompt = (
        "You are a world-class DSA curriculum designer. Your goal is to provide high-quality, "
        "LeetCode-style boilerplate code. The user expects professional signatures, appropriate return types, "
        "and perfect formatting for top-tier platforms."
    )
    
    user_prompt = f"""
    Problem Title: {req.title}
    Problem Description: {req.description}
    
    Generate problem-specific starter code (boilerplate) for the following languages.
    CRITICAL REQUIREMENTS:
    1. **Function Name**: Derived from the title (e.g., 'Two Sum' -> 'twoSum' or 'two_sum').
    2. **Types**: Infer realistic return types and parameters from the description.
    3. **Structure**: 
        - **javascript**: `var funcName = function(...) {{ }};`. Include professional JSDoc.
        - **python**: `class Solution:\n    def funcName(self, ...):`. Use modern type hints.
        - **java**: `import java.util.*;\n\nclass Solution {{\n    public ... funcName(...) {{\n\n    }}\n}}`.
        - **cpp**: `#include <iostream>\n#include <vector>\n#include <string>\nusing namespace std;\n\nclass Solution {{\npublic:\n    ... funcName(...) {{\n\n    }}\n}};`.
        - **c**: `#include <stdio.h>\n#include <stdlib.h>\n#include <stdbool.h>\n\n... funcName(...) {{\n\n}}`.
    
    Return ONLY a JSON object with keys: 'javascript', 'python', 'java', 'cpp', 'c'. 
    Return ONLY raw JSON.
    """

    try:
        completion = await generate_groq_response_with_fallback(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(raw_text)
    except Exception as e:
        logger.error(f"Boilerplate generation failed: {str(e)}")
        # Fallback empty boilerplates
        return {
            "javascript": "/**\n * @param {any} input\n * @return {any}\n */\nvar solution = function(input) {\n    \n};",
            "python": "class Solution:\n    def solve(self, input: any) -> any:\n        pass",
            "java": "import java.util.*;\n\nclass Solution {\n    public Object solve(Object input) {\n        return null;\n    }\n}",
            "cpp": "#include <iostream>\n#include <vector>\n#include <string>\n\nusing namespace std;\n\nclass Solution {\npublic:\n    void solve(auto input) {\n        \n    }\n};",
            "c": "#include <stdio.h>\n#include <stdlib.h>\n#include <stdbool.h>\n\nvoid solve(void* input) {\n    \n}"
        }

@app.post("/generate_test_cases")
async def generate_test_cases(req: TestCaseRequest):
    logger.info(f"Generating test cases for: {req.title}")
    
    prompt = f"""
    Generate 3-4 sample test cases for the following DSA problem:
    Title: {req.title}
    Description: {req.description}
    
    Return ONLY a JSON array of objects with 'input', 'expected', and 'description' keys.
    Values should be strings. 
    Ensure 'input' and 'expected' are formatted clearly for the user to understand.
    Example for Two Sum:
    [
      {{"input": "nums = [2,7,11,15], target = 9", "expected": "[0,1]", "description": "Basic case"}},
      {{"input": "nums = [3,2,4], target = 6", "expected": "[1,2]", "description": "Middle elements"}}
    ]
    
    Return ONLY the raw JSON array.
    """
    
    try:
        completion = await generate_groq_response_with_fallback(
            messages=[
                {"role": "system", "content": "You are an expert DSA tester."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(raw_text)
    except Exception as e:
        logger.error(f"Test case generation failed: {str(e)}")
        return [
            {"input": "sample input", "expected": "sample output", "description": "Default case"}
        ]

@app.post("/mock_interview_eval")
async def evaluate_interview(req: EvalRequest):
    transcript_str = ""
    for entry in req.transcript:
        role = "Candidate" if entry['role'] == 'user' else "Interviewer"
        transcript_str += f"{role}: {entry['text']}\n"

    messages = [
        {"role": "system", "content": "You are an expert Interview Evaluator."},
        {"role": "user", "content": (
            f"Evaluate this technical interview for the role of {req.role or req.domain}.\n"
            f"Transcript:\n{transcript_str}\n\n"
            "Return ONLY a raw JSON object string with strictly these keys: "
            "'score' (int 0-100), 'technical' (int 0-100), 'communication' (int 0-100), 'hireProbability' ('High'|'Medium'|'Low'), "
            "'feedback' (string), 'improvements' (list of strings), 'studyPlan' (list of strings)."
            "Do NOT include any markdown formatting like ```json. Just the raw object."
        )}
    ]

    try:
        completion = await generate_groq_response_with_fallback(
            messages=messages,
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        # Basic cleanup if model adds markdown
        import re
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"Interview evaluation failed: {str(e)}")
        return {"error": str(e), "score": 0, "feedback": "Evaluation failed."}

@app.post("/generate_questions")
async def generate_questions(domain: str, difficulty: str = "Medium"):
    messages = [
        {"role": "system", "content": "You are an expert technical question generator."},
        {"role": "user", "content": (
            f"Generate 5 {difficulty} level multiple-choice questions for {domain} interviews.\n"
            "Format as a JSON list of objects, each with: 'id', 'q' (question text), 'options' (list of 4 strings), 'ans' (index 0-3).\n"
            "Return ONLY the raw JSON."
        )}
    ]
    try:
        completion = await generate_groq_response_with_fallback(
            messages=messages,
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        import re
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if match:
            return {"questions": json.loads(match.group(0))}
        return {"questions": json.loads(raw_text)}
    except Exception as e:
        return {"error": str(e), "questions": []}

@app.post("/recommend_domain")
async def recommend_domain(req: RecommendDomainRequest):
    messages = [
        {"role": "system", "content": "You are a career counselor."},
        {"role": "user", "content": (
            f"A user has the following profile:\n"
            f"- Education: {req.education}\n"
            f"- Experience: {req.experience}\n"
            f"- Skills: {', '.join(req.skills) if req.skills else 'None'}\n\n"
            f"Which ONE of these IT domains is the BEST fit for them? "
            f"Available domains: {', '.join(req.available_domains)}.\n"
            "Return ONLY a JSON object with: 'recommended_domain' and 'reason' (2 sentences)."
        )}
    ]
    
    try:
        completion = await generate_groq_response_with_fallback(
            messages=messages,
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        import re
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(raw_text)
    except Exception as e:
        return {
            "recommended_domain": req.available_domains[0] if req.available_domains else "Software Engineering",
            "reason": f"Defaulting due to error: {e}"
        }

@app.post("/generate_roadmap")
async def generate_roadmap(req: RoadmapRequest):
    messages = [
        {"role": "system", "content": "You are an expert career counselor and curriculum designer."},
        {"role": "user", "content": (
            f"Generate a highly detailed, 5-step professional learning roadmap for {req.domain}.\n"
            "Formatting: Return ONLY a valid JSON array of objects. Each object must have: "
            "'phase' (string), 'description' (Detailed 3-4 sentence explanation), "
            "and 'tools' (an array of strings relevant to that phase).\n"
            "Return ONLY the raw JSON."
        )}
    ]
    try:
        completion = await generate_groq_response_with_fallback(
            messages=messages,
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        import re
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if match:
            return {"roadmap": json.loads(match.group(0))}
        return {"roadmap": json.loads(raw_text)}
    except Exception as e:
        return {"roadmap": [{"phase": "Learning Path", "description": f"Error: {e}", "tools": []}]}

@app.post("/generate_lesson")
async def generate_lesson(req: LessonRequest):
    domain_lessons = LESSON_LIBRARY.get(req.domain, {})
    static_lesson = domain_lessons.get(req.topic)
    
    if static_lesson:
        return static_lesson

    messages = [
        {"role": "system", "content": (
            f"You are a world-class IT teacher and curriculum designer specializing in {req.domain}. "
            "Your goal is to produce premium, high-impact learning content that feels state-of-the-art."
        )},
        {"role": "user", "content": (
            f"Generate a master-level lesson for: '{req.topic}' at a {req.difficulty} level.\n\n"
            "### CONTENT REQUIREMENTS:\n"
            "1. 'theory': Deep technical dive in Markdown. Use bold headers, highlights, and clear structure. NO solution code here.\n"
            "2. 'editorial': Optimal JavaScript code solution with detailed line-by-line logic explanation.\n"
            "3. 'description': Concise problem statement including constraints and objective.\n"
            "4. 'examples': MUST use Markdown tables for Input vs Output. Example:\n"
            "| Input | Output | Explanation |\n"
            "| :--- | :--- | :--- |\n"
            "| `n = 2` | `2` | 1+1 or 2 |\n"
            "5. 'exercise': A call-to-action statement for the student.\n"
            "6. 'solution_stub': A clean starter function template. **IMPORTANT: Never leave this empty.** Ensure function names are logical (e.g., 'climbStairs' or 'solution').\n"
            "7. 'testCases': Array of >=3 objects. Each MUST have:\n"
            "   - 'input': Valid JS expression to call the function (e.g., 'solution(5)'). **CRITICAL: DO NOT include labels like 'input:' or variable names unless they are part of a valid function call expression.**\n"
            "   - 'expected': The raw JS value expected (e.g., '8' or '[1,2]').\n"
            "   - 'description': Why this case is important.\n"
            "8. 'quiz': 3 high-quality conceptual questions.\n\n"
            "### CRITICAL RULES:\n"
            "- NO SOLUTIONS in 'theory' or 'description'.\n"
            "- 'testCases[i].input' must use the EXACT function name from 'solution_stub'.\n"
            "- 'testCases[i].input' MUST be a single line JS expression that returns a value when executed after the user's code.\n"
            "- ALL code blocks in Markdown must use proper syntax highlighting.\n\n"
            "Return ONLY a raw JSON object string."
        )}
    ]
    
    try:
        completion = await generate_groq_response_with_fallback(
            messages=messages,
            stream=False
        )
        raw_text = completion.choices[0].message.content.strip()
        import re
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_text)
    except Exception as e:
        return {"error": str(e), "theory": "Error generating lesson dynamically."}

@app.get("/problems/{domain}")
def get_problems(domain: str):
    domain_data = LESSON_LIBRARY.get(domain, {})
    if not domain_data:
        return {"problems": []}
    
    problems = []
    for name, data in domain_data.items():
        problems.append({
            "name": name,
            "subject": data.get("subject", "General"),
            "topic": data.get("topic", "General"),
            "difficulty": data.get("difficulty", "Medium"),
            "type": data.get("lesson_type", "theory")
        })
    return {"problems": problems}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
