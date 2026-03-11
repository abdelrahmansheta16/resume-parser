from app.api.schemas import ParsedJobDescription, ParsedResume
from app.extraction.resume_structurer import structure_resume
from app.matching.jd_parser import parse_job_description
from app.matching.scoring import (
    compute_education_match,
    compute_experience_match,
    compute_skill_match,
    get_recommendation_label,
    score_candidate,
)
from app.matching.ranking import rank_candidates


class TestJDParser:
    def test_basic_parsing(self, sample_jd_text):
        jd = parse_job_description(sample_jd_text)
        assert jd.title is not None
        assert len(jd.required_skills) > 0
        assert jd.required_years_experience is not None

    def test_extracts_skills(self, sample_jd_text):
        jd = parse_job_description(sample_jd_text)
        skill_names_lower = [s.lower() for s in jd.required_skills]
        assert any("python" in s for s in skill_names_lower)

    def test_extracts_years(self, sample_jd_text):
        jd = parse_job_description(sample_jd_text)
        assert jd.required_years_experience == 5.0


class TestSkillMatch:
    def test_full_overlap(self):
        resume = ParsedResume(skills=["Python", "Docker", "SQL"])
        jd = ParsedJobDescription(required_skills=["Python", "Docker", "SQL"])
        score, matched, missing = compute_skill_match(resume, jd)
        assert score == 100.0
        assert len(missing) == 0

    def test_partial_overlap(self):
        resume = ParsedResume(skills=["Python", "Docker"])
        jd = ParsedJobDescription(required_skills=["Python", "Docker", "SQL", "Kubernetes"])
        score, matched, missing = compute_skill_match(resume, jd)
        assert 0 < score < 100
        assert len(missing) > 0

    def test_no_overlap(self):
        resume = ParsedResume(skills=["Java", "Spring Boot"])
        jd = ParsedJobDescription(required_skills=["Rust", "Go"])
        score, matched, missing = compute_skill_match(resume, jd)
        assert score == 0.0


class TestExperienceMatch:
    def test_meets_requirement(self):
        resume = ParsedResume(total_years_experience=6.0)
        jd = ParsedJobDescription(required_years_experience=5.0)
        score = compute_experience_match(resume, jd)
        assert score == 100.0

    def test_below_requirement(self):
        resume = ParsedResume(total_years_experience=2.0)
        jd = ParsedJobDescription(required_years_experience=5.0)
        score = compute_experience_match(resume, jd)
        assert score < 100.0


class TestEducationMatch:
    def test_meets_requirement(self):
        from app.api.schemas import EducationSchema
        resume = ParsedResume(education=[EducationSchema(degree="Master of Science")])
        jd = ParsedJobDescription(education_requirements=["Master's degree preferred"])
        score = compute_education_match(resume, jd)
        assert score == 100.0


class TestRecommendationLabels:
    def test_labels(self):
        assert get_recommendation_label(90) == "Strong Match"
        assert get_recommendation_label(75) == "Good Match"
        assert get_recommendation_label(60) == "Moderate Match"
        assert get_recommendation_label(45) == "Weak Match"
        assert get_recommendation_label(30) == "Poor Match"


class TestEndToEnd:
    def test_score_candidate(self, sample_resume_text, sample_jd_text):
        resume = structure_resume(sample_resume_text, include_raw=True)
        jd = parse_job_description(sample_jd_text)
        match = score_candidate(resume, jd)
        assert match.match_score > 0
        assert match.recommendation != ""
        assert len(match.explanation) > 0

    def test_rank_candidates(self, sample_resume_text, sample_resume_text_2, sample_jd_text):
        r1 = structure_resume(sample_resume_text, include_raw=True)
        r2 = structure_resume(sample_resume_text_2, include_raw=True)
        jd = parse_job_description(sample_jd_text)
        ranking = rank_candidates([r1, r2], jd)
        assert len(ranking.candidates) == 2
        # Should be sorted by score descending
        assert ranking.candidates[0].match_score >= ranking.candidates[1].match_score
