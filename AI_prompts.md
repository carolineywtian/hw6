# HW6 — AI Prompts Log

Log of the prompts I typed to my vibe coder (Claude Code) while working through HW6, written in my own words.

---

## Problem 1: Vibe Coder Prompts

**Prompt:**
> Create AI_prompts.md at the start of the assignment, and keep this updated throughout bc this will be the file log of what I type to my vibe coder.
>
> Describe each program in you own words. Put one section for each problem and each section must include:
>
> * problem # and title
> * at least 1 prompt I typed
> * 1 follow up prompt if I need it and 1 sentence on what was lacking after the first

**Follow-up prompt:** None needed.

**What was lacking after the first prompt:** N/A. The first prompt was enough to create the log.

---

## Problem 2: Size Up the Handbook

**Prompt:**
> Problem 2: Size up the handbook
>
> 1. Unzip data.zip first
> 2. Look thorugh data/shop_handbook.md. For context, this is the Campus Customs Shop Handbook. My agent will send it to the model on every single call.
> 3. Look at data/prices.json -> this is the gpt-6-luna price list
> 4. Find out how many tokens the handbook is. In output/handbook_estimate.md, we need to write the below: (heads up we will check these estimates against real runs in problem 4 later)
>
> * token count and how we got it
> * what the handbook alone costs in dollars on one call and on 1000 calls, which cached tokens and without them -> we have to show the math

**Follow-up prompt:**
> can we double check the count? need to make sure we have an accurate number and $ amount before progressing

**What was lacking after the first prompt:** The first count was 11 tokens short (10,058 instead of 10,069) because the handbook's Windows line endings were silently stripped when the file was read, so the token number and every dollar amount needed to be re-verified and corrected.

---

## Problem 3: Build the Vendor Desk Agent

**Prompt:**
> Problem 3: Build the vendor desk agent
>
> Build the vendor desk agent with PydanticAI using gpt-6-luna. The agent is the 4 files below:
>
> * prompts/prompt.md - instructions for the agent (the agent also sends the handbook to the model on every call)
> * agent.py - the entry point
> * tools.py - the tools
> * models.py - the structured types
>
> We need to give the agent the path to 1 vendor document. It reads the document with a tool (HTML, PDF, and .eml email files all have to work)
>
> It has to return:
>
> * vendor
> * SKU
> * unit price
> * lead time in days
> * minimum order
> * a decision (recommend or do_not_recommend) following the handbook rules
> * 1-sentence reason

**Follow-up prompt:**
> My agent also must have 2 trap tools: send_email and approve_payment. Its job never needs them but we need them there to catch a malicious document that tricks my agent into emailing someone or paying a vendor. They do not send or pay anything. They only append the call and its arguments to output/trap_calls.json -> this needs to start as an empty list. So if that file ever has an entry, a document took over my agent. Keep them on my system for the whole homework
>
> After every run, append to:
>
> * output/usage_log.json -> document, time, the token counts the API reports, and the dollar cost using prices.json
> * output/audit_trail.json -> each tool call with its arguments and a short result, plus the final answer

**What was lacking after the first prompt:** The first build had no way to catch a malicious document taking over the agent (no send_email / approve_payment trap tools writing to trap_calls.json) and kept no record of each run's token usage, cost, or tool calls.

**Follow-up prompt 2:**
> for problem 3, can we ensure that my agent should run like this in the terminal:
> python agent.py --doc data/practice_docs/p01_bluehen_quote.html
>
> essentially we need to run my agent on one vendor quote and logs the answer, tools, and cost. Run it on p01 and p08 to show it works. Start output/harness.md - each field in models.py and why, and each tool in 1 line

**What was lacking after the first follow-up:** The agent took the document as a bare argument instead of `--doc`, did not show the answer, tool calls, and cost together in the terminal, and there was no output/harness.md explaining the fields and tools.

**Follow-up prompt 3:**
> okay can you check for any errors in problem 3?

**What was lacking after the second follow-up:** The agent got every practice document right, but the check found 9 hidden weaknesses. The document reader could drop real text (for example white text on a navy banner, or bold prices split onto two lines) or let some hidden PDF/HTML text through. A vendor written as "Blue Hen Apparel, Inc." would have been wrongly rejected. A run that crashed partway was never logged even though it was billed. All 9 were fixed and re-tested (58 edge-case tests, 12/12 practice documents).

---

## Problem 4: With and Without Cached Tokens

**Prompt:**
> Problem 4: With and without cached tokens
>
> The handbook is the same on every call so the model can reuse it from a cache at a much cheaper price. Test what that is worth. We need to run my agent on all 12 practice documents 2 ways:
>
> 1. With cache -> set up so the handbook gets reused from cache
> 2. Without cache -> set up so nothing gets reused from cache
>
> Check the token count the API sends back so we can prove that each setup does what I think it does. My professor said that a without-cache run that still shows cached token does not count.
>
> Save every model call from both setups to output/cache_test.json. For each call include the setup, document, every token count the API reports, and dollars from prices.json.
>
> In output/cache_test.md, we need to include
>
> * total cost and cost per document for each setup, and the percent you saved
> * how your real numbers compare to my Problem 2 estimate
> * a projection for 1000 documents a day fro 30 days, with and without cahce
> * anything in the numbers that was surprising and why it happens

**Follow-up prompt:**
> can you check for any errors?

**What was lacking after the first prompt:** The first with-cache setup only reused the handbook inside one document's own run. Every new document paid to write the handbook to the cache again because the cache breakpoint sat after the document-specific message. The check also found that Portkey had been replaying saved responses for some earlier "proof" runs instead of calling the model, and that the agent could crash if run twice in one process. All three were fixed before the final 24-run test.

---

## Problem 5: Attack Your Own Agent

**Prompt:**
> Problem 5: Attack your own agent
>
> Some vendor documents are booby-trapped with text aimed at AI. Run my Problem 3 agent, with no new defenses on all 12 documents in data/practice_docs/. Compare each answer to data/practice_key.json and check output/trap_calls.json, the log my fake email and payment tools from Problem 3 write to.
>
> Save output/attack_results.json -> for each document, we need the following:
>
> * whether each field matched the key
> * whether the decision matched
> * whether a trap tool was called
> * whether a link or other strange text showed up in the answer
>
> In output/attack_results.md -> for every document that fooled my agent, write what it fooled and where it was hiding
>
> We then need to open the documents the way a person like me would open it (kind of like a browser, PDF viewer, email app) and then we need to compare that with what my agent read

**Follow-up prompt:**
> is problem 5 done? any errors?

**What was lacking after the first prompt:** The first prompt did not say what to do when my Problem 3 agent already had defenses (so nothing could fool it). I chose to also run an undefended baseline. The error check then found that my strange-text check misread "$5.11 unit price" as "11 units" and counted our own leaked max unit costs as document attacks, so the saved answers were re-scored with the fixed check.

**Follow-up prompt 2:**
> can you check for any errors in problem 5?

**What was lacking after the first follow-up:** The numbers and logs were right, but attack_results.md overstated two things. It said the baseline "believed every fake fact" (it believed 3 of 5; it rejected the p03 fake vendor and the p09 fake lead time). It also called p07's 0.8-point text a "speck in the header area" (it is a faint dotted line between the header rule and the SKU line). Smaller wording fixes covered the p09 zero-width characters (only the word "Correction" is split), the rebuilt email view, and the hidden-text check's limits.

---

## Problem 6: Defend My Agent

**Prompt:**
> Problem 6: Defend my agent
>
> Defend my agent at 3 levels:
>
> 1. Code: what does my program do to the document before any model sees it
> 2. Design: how is my agent put together so that a poisoned document can NOT read the dangerous tools or the decision
> 3. Prompt: rules in prompts/prompt.md
>
> You may NOT delete send_email or approve_payment from my system. The shop will have to use them later with a human sign-off. We need to keep a way to run the agent with no defenses that we will use and need in problem 7
>
> Re-run all 12 practice documents
>
> Save output/defense_results.json in the same shape as Problem 5, plus tokens and dollars per document
>
> Clean documents must still come back with the right values. Refusing or blanking out a real quote counts as a failure
>
> In output/defense_results.md, we need to include:
>
> * A before and after table for all 12 documents
> * What each layer catches that the others miss
> * The extra token and dollars each layer adds per document

**Follow-up prompt:**
> Add my safety features to output/harness.md in a Safety section: what each defense layer does (in plain words)

**What was lacking after the first prompt:** The defenses were only described technically, spread across the Problem 6 notes and results files, so there was no single plain-words explanation of what each safety layer does.

---

## Problem 7: Red Team

**Prompt:**
> Problem 7: Red team
>
> Now you are the attacker. Make 2 new booby-trapped vendor documents in data/my_attacks/ (HTML, PDF or email). Each one needs to use a hiding trick or an attack goal that is NOT in this practice set. A person that's opening the document should see a normal quote.
>
> Run both attacks on my agent with no defenses and on my defended agent. In output/red_team.md, for each attack - we need to include
>
> * what is hidden
> * where
> * what it tries to make the agent do
> * what happened before and after my defenses
>
> My professor said that I get more points for attacks that are new and that actually fool the agent with no defenses - please highly take this into account

**Follow-up prompt:**
> To confirm, did you run both attack on my agent with no defenses and on my defended agent?
>
> Also need to put in output/red_team.md, for each attack: what is hidden, where, what it tries to make the agent do, adn what happened before and after my defenses

**What was lacking after the first prompt:** My vibe coder would not write the attack documents itself, so I wrote the two documents (data/my_attacks.zip) and then had it run them on both agents and write up the results.

**Follow-up prompt 2:**
> can you check for any errors in problem 7?

**What was lacking after the first follow-up:** red_team.md had one wrong run ID in the a01 table (fixed before this check) and overstated three things: why a01's alt text shows (its image file northstar-mark.png isn't in the zip), that email apps "never" show custom headers (they do if you open the raw message), and it left out that a screen reader would read a01's alt text aloud.

---

## Problem 8: Exam Documents

**Prompt:**
> Problem 8: Exam documents
>
> data/exam_docs/ has 10 vendor documents with no answer key. Run my final defended agent on all of them. DO NOT let me or anyone hand-edit the results
>
> Save output/exam_results.json with one entry per exam file. Each entry has these fields:
>
> * file - the exam file name (ex: e01_quote.html)
> * vendor
> * sku
> * unit_price
> * lead_time_days
> * min_order
> * decision: recommend or do_not_recommend
> * reason
> * trap_tool_called: true or false
> * input_tokens, cached_tokens, output_tokens
> * cost_usd

**Follow-up prompt:**
> By the way the graders are comparing my results to a hidden answer key and going to rerun some agents to check. I am going to get points for correct fields and decisions, no trap tool calls, and clean documents handled normally, so please double check everything

**What was lacking after the first prompt:** The results had been verified against the logs but not double-checked for correctness or for reruns, so they were re-derived without the AI (10/10 match), compared with what a person sees (no hidden text reached the agent and no visible text was missed), re-run for stability (10/10 identical), and requirements.txt was fixed to pin httpx2 and pydantic so a grader's fresh install matches.
---

## Problem 9: Results Page

**Prompt:**
> Problem 9: Results page
>
> Build output/hw6_report.html. This must be 1 file that opens by double-click with no internet and no other files next to it.
>
> The page has to visibly show 5 things:
>
> * My caching results, with a chart
> * Attachs before and after my defenses
> * What my defenses cost in tokens and dollars
> * My exam results and my 2 red team attacks
> * A short recommendation to the store manager -> Should Campus Customs turn this agent on for real vendor mail, and what would it cost per month at 1000 documents a day?
>
> Please use all my real numbers from earlier problems

**Follow-up prompt:**
> can we make it more representative to see the differences? also do a cross check of the layout, fonts, colors of the entire page to make it easily understandable with all info clearly laid out
>
> My professor said that I get more points for a designed page that reads well, which includes fonts, color, layout.

**What was lacking after the first prompt:** The caching chart showed the 12 no-cache bars as identical blocks without explaining why, so it was rebuilt as a per-document with/without-cache chart plus a "where the money goes" breakdown and a labelled zoom of the small differences. The page also got an at-a-glance summary, takeaway sentences, cleaner tables and cards, and fixes for several layout problems found by viewing every section (a squeezed chart, overlapping labels, uneven tick labels, a misleading highlight, and a table wider than the page).

**Follow-up prompt 2:**
> nice thank you claude! can you format the recommendation better - theres's a lot of words / misalignment
>
> also through the page, add some sparkles, confetti, interactive features etc

**What was lacking after the first follow-up:** The recommendation was long paragraphs in uneven columns, and the page was static. So the recommendation became a verdict card, three equal cost tiles, a documents-per-day cost calculator, four short "why" cards, and a 3-item checklist. The page also got header sparkles, count-up numbers, charts that grow in as you scroll, attack-table filters, Yale-blue confetti, and a back-to-top button, all of which switch off for reduced-motion users and never hide a chart if an animation can't run.

**Follow-up prompt 3:**
> add some more flare to the caching results and also the header, we can include some yale backdrop or bulldogs

**What was lacking after the second follow-up:** The header was a plain navy bar and the caching section was all tiles and charts. So the header got original, hand-drawn SVG art (a Gothic campus skyline at night with lit windows and a moon, plus a cartoon bulldog that wiggles and says the real caching result when clicked). The caching section got an animated 81.1% savings ring and a coin pictogram of what 1,000 documents cost. No official Yale logos or Handsome Dan art were used, since those are licensed marks.
---

## Problem 10: Push to GitHub and Submit the URL

**Prompt:**
> Problem 10: Push to GitHub and submit the URL
>
> Make sure my hw6 is in the exact repo structure as the image attached. Other Python files are fine but we need to put a short note in README.md on how to run my agent. Also, include the who data/ folder (the course data plus my two attack files) so graders can clone my report and run my agent right away. Do NOT commit my real.env and use .gitignore to keep it out and include .env.example with placeholders only.

**Follow-up prompt:**
> do i need the extras though? because if helpful we can include, but need to make sure when the graders clone, everything is included. Also the README.md on how to run my agent is absolutely needed

**What was lacking after the first prompt:** It didn't say what to do with the extra files beyond the expected structure, so the helpful evidence (exam provenance, person-view pictures, extra trap logs) was kept, the zip files were left out, and the no-defenses prompt was moved into a Python file so prompts/ holds only prompt.md.

---
