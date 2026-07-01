# ai201-project4-provenance-guard

This system analyzes creative text content to classify as AI text, human text, or unable to distinguish. It will score confidence and provide labels to users.

# Architecture overview

In the submission flow, the text content is passed to two signals: LLM Classification and Stylometric Heuristics evaluation. Each of these provide a score from 0.0-1.0 in terms of probability is AI. These scores are combined to provide a final confidence score and attribution. These sub-scores and the LLM classification reasoning are passed to an LLM to determine a transparency label. All data is logged in the audit log and score and label is returned to the user.

The appeal flow allows creators to contest their classification by taking their content ID and reasoning, updating the entry's status, and appending this as a new entry to the audit log.

```
===========================================================================
1. SUBMISSION FLOW (POST /submit)
===========================================================================

                 [ User Text Input ]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   [ Signal 1 ]                     [ Signal 2 ]
  get_LLM_score()             get_stylometric_score()
        │                                 │
        ▼ (llm_score, llm_reasoning)      ▼ (stylometric_score)
        │                                 │
        └────────────────┬────────────────┘
                         ▼
             [ Confidence Scoring ] ───► (confidence, attribution)
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[ Transparency Label ]              [ Audit Log ]
   generate_label()                   log_event()
   INPUTS:                            INPUTS:
   - llm_score                        - confidence
   - stylometric_score                - label
   - llm_reasoning                    - llm_score
   - attribution                      - stylometric_score
        │                             - attribution
        ▼ (label)                     - status="classified"
        │                                 │
        │                                 ▼
        │                         (JSON Object)
        │                         - content_id
        │                         - attribution
        │                         - confidence
        │                         - label
        │                                 │
        └────────────────┬────────────────┘
                         ▼
              [ API JSON Response ]
              (content_id, attribution, confidence, label)


===========================================================================
2. APPEAL FLOW (POST /appeal)
===========================================================================

     [ content_id + creator_reasoning ]
                     │
                     ▼
             [ Status Update ] ───► (status="under_review")
                     │
                     ▼
               [ Audit Log ]
              update_event()
              INPUTS:
              - content_id
              - creator_reasoning
              - status="under_review"
                     │
                     ▼
               (JSON Object)
               - content_id
               - status
               - message
                     │
                     ▼
           [ API JSON Response ]
           (content_id, status, message)
```

# Detection signals

Signal 1: `LLM-based classification`

Function: get_LLM_score()

Measures: Captures the semantic meaning the context, tone, and how ideas flow. Human writing is often more neuanced and unpredictable involving more diverse language use and informal transitions. While AI writing, it more predictable and formulaic with typically more use of structured transition phrases.

Limitations: It can be blinded to text that sounds human like, while missing the uniform structure of the text.

Usage: Analyzes the text input given and outputs a confidence score between 0.0 (human-written) and 1.0 (AI-generated) with a brief 1-2 sentence explanation. The output will formated as a JSON with reasoning appearing first and then llm_score.

Signal 2: `Stylometric heuristics`

Function: get_stylometric_score()

Measures: Captures 3 statistical patterns: the sentence length variation, use of unique words in the type-token ratio, and special punctuation marks utilized. Typically human writing will use more sentences of various lengths, diverse vocabulary, and varied punctuation pacing. While AI writing, will use more uniform sentence length, less diverse vocabulary, and flat or sparse punctuation usage.

Limitations: It does not focus on the actual words utilized in the text so can miss key contextual clues. These metrics could be inconsistent if either type of writing differs from typical structure such as human writing like blog posts which use more common vocabulary or simplified punctuation.

Usage: Calculates the probability score between 0.0 (human-written) and 1.0 (AI-generated) by averaging the three stylometric statistics. It first finds sentence length variation by averaging the squared differences of each sentence from the mean length, normalizing and limiting to 100, and inverting by 1.0-score so uniform sentence lengths yield a higher AI probability. Finds vocabulary diversity by dividing unique words by total word count and inverts 1.0-score so more common phrasing is attributed to higher AI probability. Lastly, it finds punctuation diversity by counting expressive marks (commas, semicolons, colons, hyphens, and em-dashes) per sentence, normalizing against a benchmark of 1.5 advanced marks, and inverting the score so minimal or flat punctuation density flags a higher AI probability.

# Confidence scoring

The score represents: how confident is this text AI-generated? This scoring setup is designed to trust the author and avoid falsely accusing a human writer. The final score is calculated by giving a 60% weight to the LLM semantic score and a 40% weight to the stylometric score; since AI could micmic human stylometrics or humans could also write more uniformly this is why more emphasis is placed on semantic meaning of the text. This combined score was then used to sort the text into clear categories based on the level of certainty. It fails gracefully if only one score can be processed this will be given 1.0 weight and set to the confidence score.

total confidence score = (0.6 _ LLM score) + (0.4 _ stylometric score)

```
0.0 -------------- 0.45 ------------ 0.65 ------------- 1.0
|   likely-human     |    uncertain    |   likely-AI    |
```

Originally, I had the cutoff for likely-human to 0.5 and uncertain to 0.8. After testing with various human-written and AI-generated text, I noticed that human text was scoring higher than expected for the stylometric score, so AI-generated text that used similar structure could be incorrectly classified as likely-human. Also, for AI-generated text the uncertain threshold was originally added to avoid false positives, but as a result AI-text was not get classified correctly; therefore, this threshold got lowered.

Example 1: "The Red Wheelbarrow" by William Carlos Williams

Input:
"so much depends\n"
"upon\n"
"a red wheel\n"
"barrow\n"
"glazed with rain\n"
"water\n"
"beside the white\n"
"chickens."

Output:
{
"attribution": "likely human-written",
"confidence": 0.27,
"content_id": "26b62e5b-f300-4066-9cd3-a646d1e2f308",
"label": "We found distinctive, nuanced language and a unique poetic structure with fragmented imagery, which strongly matches the creative variability and unpredictability characteristic of human writing."
}

Example 2: AI-Written on Photosynthesis

Input:
"Photosynthesis is a critical biological process that allows autotrophic organisms to convert light energy into chemical energy. During this reaction, plants absorb carbon dioxide from the atmosphere and water from the soil. Furthermore, chlorophyll pigments within the chloroplasts capture solar photons to synthesize glucose molecules. This essential sugar provides sustainable nourishment for metabolic growth. In conclusion, the generation of oxygen as a byproduct remains vital for global ecosystem respiration."

Output:
{
"attribution": "likely AI-generated",
"confidence": 0.76,
"content_id": "fde4d297-6fb7-4b98-99d5-b3ac1344f60e",
"label": "We found a highly structured and formulaic tone with predictable sentence patterns and transitional phrases, which strongly matches the characteristics of AI-generated writing."
}

# Transparency label

Using LLM to generate customized labels per text from the LLM reasoning provided from signal 1 and the two signal scores generated. Here are the examples of each label definition provided to the LLM:
attribution: `likely AI-generated`
label: We found highly predictable phrasing alongside a lack of variation in sentence length and vocabulary, which strongly matches AI-generated writing.

attribution: `likely human-written`
label: We found natural contextual phrasing and dynamic variation in both sentence length and vocabulary, which cleanly matches human writing.

attribution: `uncertain`
label: We detected a mix of natural word choices alongside rigid, uniform sentence structures. Because the layout lacks clear certainty, please submit an appeal for review.

# Rate limiting

the limits you chose and your reasoning for those specific values (capture rate limit responses)
I choose to limit to 10 submit, appeal, and log requests per minute; this way the system doesn't get overloaded if multiple users are trying to submit their requests. I also kept the per day limits small because creators tend to take time with producing their work, so a larger number did not feel necessary. For submit and appeal, this is limited to 25 per day and log to 50 per day.

If try to send 12 submit requests rapidly, then here is output:

```
127.0.0.1 - - [30/Jun/2026 22:50:11] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:11] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:12] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:13] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:14] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:16] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:17] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:18] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:19] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:19] "POST /submit HTTP/1.1" 200 -
127.0.0.1 - - [30/Jun/2026 22:50:19] "POST /submit HTTP/1.1" 429 -
127.0.0.1 - - [30/Jun/2026 22:50:20] "POST /submit HTTP/1.1" 429 -
```

# Known limitations

Since the system is designed in favor of human-written work, AI-generated work that is made to follow human semantics and structure will be incorrectly classified as human work. Given that AI is trained on human work, this makes it harder to detect this as AI created when the AI purposefully incorporates the features of human writing that make it distinguishable.

Example 1: Human Mimicking AI-generated

Input:
"Look, let's be entirely real for a second. The collective soul of America isn't defined by partisan bickering on cable news. It's found in the quiet, everyday resilience of ordinary folks. Yeah, things are incredibly messy right now—inflation is squeezing wallets, communities are fractured, and parents are genuinely scared about what comes next. But there's this underlying grit here. It's a messy, imperfect hope that doesn't just disappear when things get tough. That's the real story."

Output:
{
"attribution": "likely human-written",
"confidence": 0.28,
"content_id": "164a3110-1f6c-4780-8cf7-7368e3a3c379",
"label": "We found a writing style that closely matches human expression, characterized by a nuanced tone, conversational language, and the use of colloquial expressions, which strongly indicates human authorship."
}

Example 2: AI-Generated Human Essay adapted from Reddit (r/IELTS)

Input:
"There are many reasons why people choose to study abroad. First of all, living in another country helps a student learn a new language much faster. Second, it provides an excellent opportunity to experience different cultures and traditions. In addition, having an international degree makes it much easier to find a high-paying job later. Therefore, despite the high costs, studying in a foreign university is a very good choice for the soul and future."

Output:
{
"attribution": "uncertain",
"confidence": 0.65,
"content_id": "4abaac57-dc5e-4701-809f-c1dc92d98e41",
"label": "We detected a predominantly formulaic writing structure with predictable transitional phrases and straightforward language, which suggests AI-generated characteristics, but the overall classification remains uncertain due to inconsistent scoring indicators."
}

# Spec reflection

The Architecture section helped me to frame my thinking to understand the overall big picture. I was able to see all inputs and outputs to make sure all key data points were accounted for. This also provided a great roadmap for AI tool to follow when creating the production level app.

I ended up adding another stylometric heuristic that capture use of specialized punctuation to enhance the stylometric scoring metric and help with distiguishing human vs AI text.

# AI usage section

Example 1:

I advised Gemini to implement my signal 2 stylometric heuristics functionality and provide test cases to see how well this score performs.
What changed: After, I factored this into my confidence scoring functionality I noticed that the stylometric score was not providing good separation between the human vs AI text. I re-prompted and per suggestion from AI added an additional specialized punctuation metric factored into the stylometric score.

Example 2:

I prompted Gemini to implement transparency label functionality and provide test cases.
What changed: I tried and re-prompted with different prompts before I got one prompt template that return results consistent with what I expected.
