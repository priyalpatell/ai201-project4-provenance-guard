import os
import re
import json
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

def get_LLM_score(text: str) -> dict:
    """
    Analyzes text semantics, tone, and flow using a Groq LLM.
    Returns an ordered dictionary with 'llm_reasoning' appearing first, 
    followed by 'llm_score'. If an error occurs, llm_score is set to -1.0.
    """
    if not GROQ_API_KEY:
        return {
            "llm_reasoning": "Error running LLM semantic analysis: GROQ_API_KEY config missing.",
            "llm_score": -1.0
        }

    try:
        client = Groq(api_key=GROQ_API_KEY)

        system_prompt = (
            "You are an expert AI text detector analyzing semantic flow, tone, and predictability. "
            "Human writing is nuanced, unpredictable, and uses informal transitions. "
            "AI writing is formulaic, highly predictable, and relies on structured transitions. "
            "Analyze the input text and return a strict JSON object with exactly two keys in this order:\n"
            "1. 'llm_reasoning': A brief 1-2 sentence explanation of your analysis.\n"
            "2. 'llm_score': A float between 0.0 (completely human-written) and 1.0 (completely AI-generated).\n\n"
            "CRITICAL: Do not include any markdown formatting, backticks, or text outside the JSON object."
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this text:\n\n{text}"}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return {
            "llm_reasoning": result.get("llm_reasoning", "No reasoning provided."),
            "llm_score": float(result.get("llm_score", 0.5))
        }

    except Exception as e:
        return {
            "llm_reasoning": f"Error running LLM semantic analysis: {str(e)}",
            "llm_score": -1.0
        }

def get_stylometric_score(text: str) -> float:
    """
    Calculates an AI probability score between 0.0 and 1.0 based on 
    the average of sentence length variance and type-token ratio (TTR).
    Returns -1.0 if the calculation cannot be performed due to empty input or error.
    """
    stripped_text = text.strip()
    if not stripped_text:
        return -1.0

    try:
        # --- 1. SENTENCE PREPARATION & VARIANCE CALCULATION ---
        sentences = [s.strip() for s in re.split(r'[.!?]+', stripped_text) if s.strip()]
        if not sentences:
            return -1.0

        sentence_lengths = [len(s.split()) for s in sentences]
        total_sentences = len(sentence_lengths)
        mean_length = sum(sentence_lengths) / total_sentences

        squared_diffs = [(length - mean_length) ** 2 for length in sentence_lengths]
        variance = sum(squared_diffs) / total_sentences

        normalized_variance = min(variance / 100.0, 1.0)
        sentence_ai_score = 1.0 - normalized_variance

        # --- 2. VOCABULARY DIVERSITY (TYPE-TOKEN RATIO) ---
        words = re.findall(r'\b\w+\b', stripped_text.lower())
        total_word_count = len(words)
        
        if total_word_count == 0:
            return -1.0

        unique_word_count = len(set(words))
        type_token_ratio = unique_word_count / total_word_count
        vocabulary_ai_score = 1.0 - type_token_ratio

    # --- 3. NEW: PUNCTUATION DIVERSITY METRIC ---
        # Count expressive punctuation marks: commas, semicolons, colons, hyphens, and em-dashes
        expressive_punctuation = re.findall(r'[,;:—\-]', stripped_text)
        punctuation_count = len(expressive_punctuation)
        
        # Ratio of special punctuation per sentence
        punct_ratio = punctuation_count / total_sentences
        # Normalize against a benchmark (e.g., an average of 1.5 advanced marks per sentence indicates high human variance)
        normalized_punct = min(punct_ratio / 1.5, 1.0)
        # Inverted: Minimal or flat punctuation usage yields a higher AI probability
        punctuation_ai_score = 1.0 - normalized_punct

        # --- 4. FINAL COMBINED SCORE ---
        # Average all three components together
        final_stylometric_score = (sentence_ai_score + vocabulary_ai_score + punctuation_ai_score) / 3.0
        
        return round(final_stylometric_score, 2)

    except Exception:
        return -1.0

# # Execution block using the same test cases from the first signal test
# if __name__ == "__main__":
#     # Test Case 1: Actual Human Writing (President Obama Excerpt)
#     human_text = (
#         "The America I know is full of courage, and optimism, and ingenuity. "
#         "The America I know is decent and generous. Sure, we have real anxieties – "
#         "about paying the bills, protecting our kids, caring for a sick parent. "
#         "We get frustrated with political gridlock, worry about racial divisions; "
#         "are shocked and saddened by the madness of Orlando or Nice. There are pockets "
#         "of America that never recovered from factory closures; men who took pride in "
#         "hard work and providing for their families who now feel forgotten. Parents "
#         "who wonder whether their kids will have the same opportunities we have."
#     )

#     # Test Case 2: AI-Generated Content (Standard / Obvious)
#     ai_text = (
#         "The United States is characterized by a resilient population that consistently demonstrates "
#         "innovation and determination. Furthermore, citizens navigate economic challenges and community "
#         "responsibilities daily. It is important to note that industrial transitions have impacted localized "
#         "economies, resulting in workforce evolution. Consequently, addressing these socio-economic shifts "
#         "remains critical for future development and ensuring equitable progress across generations."
#     )

#     # Test Case 3: Tricky AI-Generated Content (Adversarial / Human-Mimicking)
#     tricky_ai_text = (
#         "Look, let's be entirely real for a second. The collective soul of America isn't defined by "
#         "partisan bickering on cable news. It's found in the quiet, everyday resilience of ordinary folks. "
#         "Yeah, things are incredibly messy right now—inflation is squeezing wallets, communities are fractured, "
#         "and parents are genuinely scared about what comes next. But there's this underlying grit here. "
#         "It's a messy, imperfect hope that doesn't just disappear when things get tough. That's the real story."
#     )

#     print("=== Testing Human Text Example ===")
#     human_result = get_LLM_score(human_text)
#     print(json.dumps(human_result, indent=4))

#     print("\n=== Testing AI Text Example ===")
#     ai_result = get_LLM_score(ai_text)
#     print(json.dumps(ai_result, indent=4))

#     print("\n=== Testing Tricky AI Text Example ===")
#     tricky_ai_result = get_LLM_score(tricky_ai_text)
#     print(json.dumps(tricky_ai_result, indent=4))

#     print(f"Case 1 (Human Speech) Stylometric Score:  {get_stylometric_score(human_text)}")
#     print(f"Case 2 (Standard AI) Stylometric Score:   {get_stylometric_score(ai_text)}")
#     print(f"Case 3 (Tricky AI) Stylometric Score:     {get_stylometric_score(tricky_ai_text)}")