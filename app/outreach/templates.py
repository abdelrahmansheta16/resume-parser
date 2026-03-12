from __future__ import annotations

RECRUITER_TEMPLATE = {
    "subject": "Application for {role} at {company}",
    "body": """Dear {company} Recruiting Team,

My name is {candidate_name}, and I'm writing to express my interest in the {role} position at {company}.

With {years} years of experience in {top_skills}, I believe I would be a strong fit for this role. {achievement}

I have attached my resume for your review. I would welcome the opportunity to discuss how my background aligns with your team's needs.

Thank you for your time and consideration.

Best regards,
{candidate_name}""",
}

HIRING_MANAGER_TEMPLATE = {
    "subject": "Re: {role} Position — {candidate_name}",
    "body": """Dear Hiring Manager,

I recently came across the {role} opening at {company} and am very interested in this opportunity.

My background includes {years} years of experience specializing in {top_skills}. {achievement}

I believe my experience aligns well with the requirements you've outlined, and I'd love the chance to contribute to {company}'s goals.

I've attached my tailored resume for your consideration. I'd welcome the opportunity to discuss this role further at your convenience.

Best regards,
{candidate_name}""",
}

REFERRAL_TEMPLATE = {
    "subject": "Referral Request — {role} at {company}",
    "body": """Hi,

I hope this message finds you well. I noticed that {company} has an opening for a {role}, and I wanted to reach out regarding a potential referral.

I have {years} years of experience in {top_skills}, and I believe my skills would be a great match for this position. {achievement}

If you're comfortable, I would greatly appreciate a referral or any guidance you might have about the application process.

Thank you for your time!

Best regards,
{candidate_name}""",
}

TEMPLATES = {
    "recruiter": RECRUITER_TEMPLATE,
    "hiring_manager": HIRING_MANAGER_TEMPLATE,
    "referral": REFERRAL_TEMPLATE,
}
