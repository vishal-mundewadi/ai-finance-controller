AI Settlement Investigator

AI-powered settlement reconciliation for finance operations

Built for the **Razorpay AI Builder Internship 2026 — AI Finance Controller Track**

[Live Demo](https://ai-finance-controller-amber.vercel.app) ·
[GitHub Repository](https://github.com/vishal-mundewadi/ai-finance-controller)


 What is this?
Imagine a finance team receives thousands of payment records, refund records, fee/tax records, and settlement records.
At the end of the day, they need to answer a simple question:
> "Did we receive the money we were supposed to receive?"
When the expected amount and the settled amount don't match, someone has to investigate why.
That investigation can involve manually comparing records, checking refunds, looking for missing transactions, checking settlement delays, and figuring out whether a fee or tax was applied incorrectly.

**AI Settlement Investigator automates this investigation.**
It takes payment, refund, and settlement data, reconciles the records, identifies exceptions, calculates the financial impact, and explains what happened in plain English.

## The Problem
Settlement reconciliation sounds simple:

**Expected money → Actual money → Difference**
But in real finance operations, the difference can happen for many reasons:
- A payment may be missing from a settlement.
- A settlement may arrive later than expected.
- A refund may not match the expected amount.
- Fees or taxes may be different from the expected values.
- A failed payment may appear in the payment data but should not be included in settlement expectations.
- A settlement may contain an impossible date relationship.
- Multiple edge cases can occur across thousands of transactions.

Finding these exceptions manually becomes time-consuming and difficult to scale.
## The Solution
AI Settlement Investigator turns this into an automated investigation workflow.

### The workflow

```text
Payment Records
      +
Refund Records
      +
Settlement Records
      │
      ▼
┌─────────────────────────────┐
│ Deterministic Reconciliation│
│        Engine               │
└─────────────┬───────────────┘
              │
              ▼
     Detect & classify
       discrepancies
              │
              ▼
     Calculate financial
          impact
              │
              ▼
┌─────────────────────────────┐
│       Gemini AI Layer       │
│ Explain + Recommend Action  │
└─────────────┬───────────────┘
              │
              ▼
       Finance Dashboard


The important design decision is that AI does not decide whether money is missing.
The reconciliation engine makes that decision using deterministic financial rules.
Gemini is used afterward to explain an already-detected issue and suggest the next operational action.
This keeps the financial logic predictable while still making the output easier for a finance professional to understand.


What does the user see?
The dashboard is designed around an actual investigation workflow rather than simply displaying raw data.

**AI Design**
One of the biggest risks of using an LLM for financial operations is allowing the model to invent numbers or make financial decisions.
This project deliberately separates those responsibilities.
Deterministic engine
The Python reconciliation engine is responsible for:
Financial calculations
Expected settlement calculations
Comparing records
Detecting discrepancies
Classifying discrepancy types
Calculating discrepancy amounts
Confidence scoring
Gemini

Gemini receives only the structured discrepancies already identified by the reconciliation engine.

It is responsible for:
Explaining the detected issue in plain English
Providing a concise recommended action
Making the investigation easier for a human to understand

It is explicitly instructed not to:
Invent amounts
Change transaction IDs
Change discrepancy categories
Decide whether a transaction is a discrepancy
Guess missing financial values
Reliability fallback
External AI services can occasionally be unavailable.

If the Gemini API fails, the application automatically falls back to deterministic template explanations.

This means:
AI unavailable ≠ application unavailable.
The core reconciliation workflow continues to work.

Evaluation
The project was tested using progressively larger synthetic datasets and a separate hard evaluation dataset.
The evaluation setup intentionally keeps the ground-truth labels separate from the reconciliation engine.

Evaluation Data
      │
      ▼
Reconciliation Engine
      │
      ▼
Predictions
      │
      └──────────────┐
                     ▼
              Evaluation Script
                     ▲
                     │
              Ground Truth

The reconciliation engine does not read the ground-truth file while making predictions.
The hard evaluation dataset includes adversarial cases such as:
Minor fee variances
Impossible settlement dates
Delayed settlements
Missing transactions
Refund mismatches
Fee/tax mismatches
Latest hard-evaluation result
Recall: 93.7%
Precision: 100%
False Positive Rate: 0%
This means the system was conservative about flagging transactions: every flagged discrepancy in the hard evaluation was a true positive, while some difficult edge cases were still missed.

**Tech Stack**
--> Backend
Python
FastAPI
Pydantic
Pandas
Uvicorn
Google Gemini API
---> Frontend
React
TypeScript
Vite
Tailwind CSS
Framer Motion
Deployment
Vercel
GitHub

**Architecture**
                    ┌──────────────────┐
                    │   CSV Datasets   │
                    │                  │
                    │ Payments         │
                    │ Refunds          │
                    │ Settlements      │
                    └────────┬─────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │ Reconciliation Engine │
                 │                       │
                 │ Financial Rules       │
                 │ Matching              │
                 │ Classification        │
                 │ Calculations           │
                 └───────────┬───────────┘
                             │
                             ▼
                   Structured Results
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
          ┌──────────────┐      ┌──────────────┐
          │   FastAPI    │      │   Gemini AI  │
          │   Backend    │◄────►│ Explanation  │
          └──────┬───────┘      └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │    React     │
          │  Dashboard   │
          └──────────────┘

**Project Structure**
ai-finance-controller/
│
├── backend/
│   ├── data/
│   │   ├── quick/
│   │   ├── dev/
│   │   ├── eval/
│   │   └── hard_eval/
│   │
│   ├── reconciliation_engine.py
│   ├── ai_explainer.py
│   ├── api.py
│   ├── evaluate.py
│   ├── generate_dataset_v2.py
│   ├── generate_hard_eval.py
│   └── requirements.txt
│
├── frontend/
│   └── src/
│
├── vercel.json
└── .gitignore

Build Challenges & What I Learned
1. Making financial decisions deterministic
The first design challenge was deciding where AI should and should not be used.
Using an LLM to calculate financial discrepancies would make the system difficult to trust and evaluate.
Solution: financial calculations and discrepancy detection are handled entirely by deterministic Python logic.

2. Designing realistic test data
A simple dataset is not enough to test a reconciliation system.
The project therefore uses progressively larger datasets and a separate hard evaluation dataset containing deliberately difficult cases.
This helped expose limitations in the initial rules and led to additional handling for edge cases such as impossible settlement dates.

3. Handling LLM reliability
Gemini can occasionally become temporarily unavailable.
Instead of making the entire application dependent on the AI service, the AI layer was designed as an optional explanation layer.
Solution: deterministic template explanations are used as a fallback whenever the Gemini request fails.

4. Connecting the entire workflow
The project required integrating:
Data → Python reconciliation → FastAPI → Gemini → React → Vercel
The backend exposes structured settlement-analysis results through API endpoints, and the React dashboard turns those results into an investigation interface.

Why this approach?
The project follows a simple principle:
Use deterministic logic for decisions. Use AI for understanding.
For financial operations, this separation is important.
The system should be able to explain a discrepancy without allowing an LLM to decide how much money actually exists.
That makes the architecture easier to test, easier to reason about, and safer to extend.

Future Improvements
Potential next steps include:
Batch-level investigation summaries
Historical anomaly detection
More advanced multi-issue transaction handling
Finance-team feedback loops
Support for additional settlement providers
Larger real-world evaluation datasets
Investigation history and audit trails

Live Demo AI Settlement Investigator
https://ai-finance-controller-amber.vercel.app
The live application allows users to select settlements and investigate detected reconciliation exceptions.

Built For
Razorpay AI Builder Internship 2026
Track: AI Finance Controller
Project: AI Settlement Investigator
