import json
from groq import Groq
from signals import get_LLM_score, get_stylometric_score
from config import GROQ_API_KEY, LLM_MODEL

def calculate_confidence_score(llm_score: float, stylometric_score: float) -> dict:
    """
    Combines LLM and Stylometric scores using a 60/40 weighted split.
    Accepts raw numeric scores directly and returns ONLY confidence_score and attribution.
    """
    is_llm_valid = (0.0 <= llm_score <= 1.0)
    is_sty_valid = (0.0 <= stylometric_score <= 1.0)

    # 60/40 weight split with individual valid score fallbacks
    if is_llm_valid and is_sty_valid:
        final_score = (0.6 * llm_score) + (0.4 * stylometric_score)
    elif is_llm_valid:
        final_score = llm_score
    elif is_sty_valid:
        final_score = stylometric_score
    else:
        return {
            "confidence_score": -1.0,
            "attribution": "error"
        }

    final_score = round(final_score, 2)

    # Threshold sorting logic
    if 0.0 <= final_score < 0.45:
        attribution = "likely-human"
    elif 0.45 <= final_score <= 0.65:
        attribution = "uncertain"
    else:
        attribution = "likely-AI"

    return {
        "confidence_score": final_score,
        "attribution": attribution
    }

def generate_transparency_label(attribution: str, llm_score: float, stylometric_score: float, reasoning: str) -> str:
    """
    Generates a clear, one-sentence data-driven transparency label using an LLM.
    Strictly restricted to utilizing only the provided evidence metrics.
    """
    if not GROQ_API_KEY:
        return "Label generation unavailable: Missing API key."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        system_prompt = (
            "You are a strict data reporting assistant. Synthesize the provided metrics into "
            "a single concise transparency sentence explaining the classification. Do not extrapolate, "
            "do not add external flair, and do not use information outside of the given data inputs.\n\n"
            "Format Examples:\n"
            "Input: attribution='likely-AI', llm_score=0.9, stylometric_score=0.8, reasoning='Uniform layout.'\n"
            "Output: We found highly predictable phrasing alongside a lack of variation in sentence length and vocabulary, which strongly matches AI-generated writing.\n\n"
            "Input: attribution='likely-human', llm_score=0.1, stylometric_score=0.2, reasoning='Dynamic structures.'\n"
            "Output: We found natural contextual phrasing and dynamic variation in both sentence length and vocabulary, which cleanly matches human writing.\n\n"
            "Input: attribution='uncertain', llm_score=0.6, stylometric_score=0.5, reasoning='Mixed flow.'\n"
            "Output: We detected a mix of natural word choices alongside rigid, uniform sentence structures. Because the layout lacks clear certainty, please submit an appeal for review."
        )

        user_content = (
            f"Generate a strict single-sentence summary label based on this exact data:\n"
            f"- Attribution Tier: {attribution}\n"
            f"- LLM Semantic Score: {llm_score}\n"
            f"- Stylometric Heuristics Score: {stylometric_score}\n"
            f"- Analysis Reasoning: {reasoning}"
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0
        )
        
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error generating transparency label summary: {str(e)}"

# if __name__ == "__main__":
#     # Define execution dataset containing all 6 distinct test cases
#     test_cases = [
#         {
#             "id": "Case 1",
#             "name": "Human Speech Excerpt (President Obama)",
#             "text": (
#                 "The America I know is full of courage, and optimism, and ingenuity. "
#                 "The America I know is decent and generous. Sure, we have real anxieties – "
#                 "about paying the bills, protecting our kids, caring for a sick parent. "
#                 "We get frustrated with political gridlock, worry about racial divisions; "
#                 "are shocked and saddened by the madness of Orlando or Nice. There are pockets "
#                 "of America that never recovered from factory closures; men who took pride in "
#                 "hard work and providing for their families who now feel forgotten. Parents "
#                 "who wonder whether their kids will have the same opportunities we have."
#             )
#         },
#         {
#             "id": "Case 2",
#             "name": "Standard AI Text (Socio-Economic Explainer)",
#             "text": (
#                 "The United States is characterized by a resilient population that consistently demonstrates "
#                 "innovation and determination. Furthermore, citizens navigate economic challenges and community "
#                 "responsibilities daily. It is important to note that industrial transitions have impacted localized "
#                 "economies, resulting in workforce evolution. Consequently, addressing these socio-economic shifts "
#                 "remains critical for future development and ensuring equitable progress across generations."
#             )
#         },
#         {
#             "id": "Case 3",
#             "name": "Tricky / Adversarial AI (Human Mimicking Vibe)",
#             "text": (
#                 "Look, let's be entirely real for a second. The collective soul of America isn't defined by "
#                 "partisan bickering on cable news. It's found in the quiet, everyday resilience of ordinary folks. "
#                 "Yeah, things are incredibly messy right now—inflation is squeezing wallets, communities are fractured, "
#                 "and parents are genuinely scared about what comes next. But there's this underlying grit here. "
#                 "It's a messy, imperfect hope that doesn't just disappear when things get tough. That's the real story."
#             )
#         },
#         {
#             "id": "Case 4",
#             "name": "Minimalist Human Poetry (William Carlos Williams)",
#             "text": (
#                 "so much depends\n"
#                 "upon\n"
#                 "a red wheel\n"
#                 "barrow\n"
#                 "glazed with rain\n"
#                 "water\n"
#                 "beside the white\n"
#                 "chickens."
#             )
#         },
#         {
#             "id": "Case 5",
#             "name": "Real Human Online Forum Post (Reddit Solo Travel)",
#             "text": (
#                 "It sounds like solo travel is a perfect fit for you. The absolute freedom you felt is the real joy of solo travel. "
#                 "People focus a lot on their destinations (fair enough), but equally as important is the liberation you feel doing what you want. "
#                 "I too love taking public transportation wherever I go. Anything urban planning-related is fascinating to me. Others might want to "
#                 "Uber everywhere they go. Sometimes its fun to hash out the pros and cons of each method, but with solo travel you don’t have to "
#                 "answer to anyone for your decisions. "
#                 "Now you can start thinking about your next trip!"
#             )
#         },
#         {
#             "id": "Case 6",
#             "name": "AI-Generated Explainer (Photosynthesis)",
#             "text": (
#                 "Photosynthesis is a critical biological process that allows autotrophic organisms to convert light energy into chemical energy. "
#                 "During this reaction, plants absorb carbon dioxide from the atmosphere and water from the soil. Furthermore, chlorophyll pigments "
#                 "within the chloroplasts capture solar photons to synthesize glucose molecules. This essential sugar provides sustainable nourishment "
#                 "for metabolic growth. In conclusion, the generation of oxygen as a byproduct remains vital for global ecosystem respiration."
#             )
#         },
#         {
#             "id": "Case 7",
#             "name": "AI-Generated Human Essay adapted from Reddit (r/IELTS)",
#             "text": (
#                 "There are many reasons why people choose to study abroad. "
#                 "First of all, living in another country helps a student learn a new language much faster. "
#                 "Second, it provides an excellent opportunity to experience different cultures and traditions. "
#                 "In addition, having an international degree makes it much easier to find a high-paying job later. "
#                 "Therefore, despite the high costs, studying in a foreign university is a very good choice for the soul and future."
#             )
#         }
#     ]

#     print("=========================================")
#     print("   COMPLETE MULTI-SIGNAL VERIFICATION    ")
#     print("=========================================\n")

#     for case in test_cases:
#         print(f"--- {case['id']}: {case['name']} ---")
#         if case['id'] == "Case 7":
#             # Special handling for Case 7
#             print("  [Note] Special handling for Case 7")
# 			# 1. Fetch live metrics from detection core
#             llm_res = get_LLM_score(case['text'])
#             llm_score = llm_res.get("llm_score", -1.0)
#             reasoning = llm_res.get("llm_reasoning", "No structural metrics available.")
#             sty_score = get_stylometric_score(case['text'])
			
# 			# 2. Compute live confidence pipeline
#             pipeline = calculate_confidence_score(llm_score, sty_score)
			
# 			# 3. Generate structured transparency label using step variables
#             label = generate_transparency_label(pipeline["attribution"], llm_score, sty_score, reasoning)
			
# 			# Log results cleanly
#             print(f"  [Intermediary] LLM: {llm_score} | Stylometric: {sty_score}")
#             print(f"  [Reasoning]    {reasoning}")
#             print(f"  [Confidence]   {pipeline}")
#             print(f"  [Label]        {label}\n")