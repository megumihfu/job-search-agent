from crewai import LLM
from src.config import CHATANYWHERE_API_KEY
from src.tools.linkedin_tool import LinkedInTool
from src.tools.excel_tool import ExcelExportTool
import json
import re

# LLM agent conf
llm = LLM(
    model="gpt-4o-mini",
    api_key=CHATANYWHERE_API_KEY,
    base_url="https://api.chatanywhere.tech/v1",
    temperature=0.1
)

print("LLM has been configured")

linkedin_tool = LinkedInTool()
excel_tool = ExcelExportTool()

def is_rejected_by_python(job: dict) -> tuple[bool, str]:
    #  prefilter jobs using regex
    title = job.get('position', '').lower()

    #  check seniority level
    sr_key = [
            r'\bsenior\b', 
            r'\bsr\b', 
            r'\blead\b', 
            r'\bstaff\b', 
            r'\bprincipal\b', 
            r'\barchitect\b', 
            r'\bdirector\b'
        ]
    if any (re.search(kw, title) for kw in sr_key):
        return True, "contains seniors level keywords"
    
    # check contarct
    contract_key = [
            r'\bintern\b', 
            r'\binternship\b', 
            r'\bstage\b', 
            r'\bapprentice\b', 
            r'\bapprenticeship\b', 
            r'\bapprentissage\b', 
            r'\balternance\b', 
            r'\balternant\b', 
            r'\bfreelance\b'
        ]
    if any (re.search(kw, title) for kw in contract_key):
        return True, "contains contract/intern keywords"
    
    # check stack
    stack_key = [
            r'\bphp\b', 
            r'\bnode\b', 
            r'\bnodejs\b', 
            r'\bnode\.js\b', 
            r'\bruby\b', 
            r'\bdotnet\b', 
            r'\b\.net\b', 
            r'\bc#\b',
            r'\bc\+\+'
        ]
    
    if any (re.search(kw, title) for kw in stack_key):
        return True, "contains non-allowed stack keywords"
    
    return False, ""

def run_job_agent():
    print("Starting job agent...")

    try:
        job_offers = linkedin_tool._run()
    except Exception as e:
        print(f"Error during Linkedin search: {e}")
        return
    
    print(f"\nTotal job offers fetched: ", len(job_offers))

    filtered_jobs = []
    rejected_counter = 0

    for job in job_offers:
        rejected, reason = is_rejected_by_python(job)

        if rejected: 
            rejected_counter += 1
            print(f"Rejected job: {job.get('position', '')[:40]}... Reason: {reason}")
        else:
            filtered_jobs.append(job)

    print(f"{rejected_counter} were rejected")
    print(f"Jobs remaining for LLM: {len(filtered_jobs)}")
    
    valid_jobs = []
    batch_size = 3

    try:
        for i in range(0, len(filtered_jobs), batch_size):
            batch = filtered_jobs[i:i + batch_size]
            jobs_txt = ""
        
            for index, j in enumerate(batch, 1):
                jobs_txt += f"""
--- JOB {index} ---
Position: {j.get('position')} @ {j.get('company')}
City: {j.get('location')}
Country: {j.get('target_country')}
Description: {j.get('description', 'N/A')}
"""

            prompt = f"""
ROLE: Expert IT Recruitment Screener.
CONTEXT: The candidate is looking for software development roles in France, Belgium, UK, Germany, Singapore or Malaysia.
BENEFIT OF THE DOUBT: If the job description is missing or empty, but the JOB TITLE matches (Backend, Software Engineer), keep it.

FILTERS:
1. STACK: Must include either Python, Java, or Kotlin.
2. TECH FOCUS: REJECT non-IT jobs.
3. EXPERIENCE: Entry-level to max 4 years. REJECT if title has "Senior", "Staff", "Platform" or "Lead".
4. SECTOR: Only REJECT if the COMPANY itself is a Bank, Insurance, or Defense firm.
5. CONTRACT: Permanent, temporary or V.I.E. REJECT intern/apprentice & contract.
6. LOCATION: The candidate accepts ALL cities in the target country context.
7. LANGUAGE: Check if the languages needed are ONLY French AND/OR English.
8. FINAL DECISION: If you are unsure or data is missing, the default answer is YES.

Evaluate each job below and return ONLY a valid JSON object matching this exact structure:
{{
  "1": {{"decision": "YES" or "NO", "reason": "short explanation"}},
  "2": {{"decision": "YES" or "NO", "reason": "short explanation"}}
}}

JOBS TO EVALUATE:
{jobs_txt}
"""

            try:
                response = llm.call(prompt)
                
                clean_response = response.strip()
                if "```json" in clean_response:
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    clean_response = clean_response.split("```")[1].strip()

                evals = json.loads(clean_response)

                for index, j in enumerate(batch, 1):
                    eval_data = evals.get(str(index), {})
                    decision = eval_data.get("decision", "NO")
                    reason = eval_data.get("reason", "No reason provided")
                    print(f"{j.get('position', '')[:40]}... {decision} ({reason})")

                    if "YES" in str(decision).upper():
                        valid_jobs.append(j)

            except json.JSONDecodeError:
                print(f"Warning: failed to parse JSON response at index {i}. Keeping batch by default.")
                valid_jobs.extend(batch)
                    
            except Exception as e:
                error_msg = str(e).lower()
                if any(x in error_msg for x in ["429", "limited", "too_many_requests"]):
                    print("\nAPI quota exceeded. Saving progress and exiting...")
                    break
                else:
                    print(f"Error on batch starting at index {i}: {e}")
                    continue
    
    except Exception as e:
        print(f"Unexpected crash: {e}")

    finally:
        print(f"\nClosing agent. Jobs validated: {len(valid_jobs)}")
        jobs_json = json.dumps(valid_jobs, default=str)
        result = excel_tool._run(jobs_json)
        print(result)

if __name__ == "__main__":
    run_job_agent()