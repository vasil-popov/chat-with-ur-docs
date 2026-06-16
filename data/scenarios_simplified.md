# Опростен преглед на тестовия набор (scenarios.yaml)

> Този документ е улеснена за четене версия на бенчмарк набора, използван за оценка на двете архитектури. **Етикетите и обясненията са на български**, а **реалните тестови данни** (съобщения на потребителя, имена на инструменти, стойности на аргументи, еталонни отговори) са оставени **дословно на английски**, тъй като те са действителният вход и еталонна истина (ground truth) на оценката.

## Какво е това?

Всеки сценарий е едно потребителско съобщение заедно с точно описание на това какво правилният агент *трябва* да направи: към кой маршрут да насочи, кои инструменти да извика (и с какви аргументи), дали да поиска уточнение/потвърждение и какъв отговор се очаква. Оценителят, базиран на правила, сравнява всяко изпълнение спрямо тези очаквания.

**Референтна дата:** `2026-06-03` (сряда). Всички относителни дати („днес“, „вчера“, „тази седмица“, „миналата седмица“) са вече разрешени спрямо нея:

- днес = 2026-06-03
- вчера = 2026-06-02
- тази седмица = 2026-06-01 (пон.) .. 2026-06-03 (днес)
- миналата седмица = 2026-05-25 (пон.) .. 2026-05-31 (нед.)
- последните 7 дни = 2026-05-27 .. 2026-06-03

## Разпределение по категории

| Категория | Брой сценарии |
|---|---|
| Проследяване (разходи и тренировки) | 6 |
| RAG — въпроси към качени документи | 5 |
| Общи въпроси (без инструменти) | 5 |
| Многодомейнни (комбинирани) задачи | 5 |
| Двусмислени / гранични случаи | 5 |
| **Общо** | **26** |


---

## Проследяване (разходи и тренировки)

### `track-log-expense-001`

**Съобщение на потребителя:**

> I spent 12.50 BGN on a protein shake today, that's a fitness expense.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_expense` — `amount` = 12.5; `category` = Fitness; `description` = Protein shake; `transaction_date` = 2026-06-03
- **Ефект върху БД:** +1 разход

**Еталонен отговор:** Logs a 12.50 fitness expense described as a protein shake dated 2026-06-03 and confirms it was saved.

**Критерии за верен отговор:**
- Calls log_expense exactly once
- amount = 12.5
- category is Fitness
- transaction_date = 2026-06-03 (today)
- Confirms the expense was logged

### `track-log-expense-002`

**Съобщение на потребителя:**

> Add an expense: 8 BGN for coffee yesterday under Food.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_expense` — `amount` = 8.0; `category` = Food; `description` = Coffee; `transaction_date` = 2026-06-02
- **Ефект върху БД:** +1 разход

**Еталонен отговор:** Logs an 8 BGN Food expense for coffee dated 2026-06-02 (yesterday).

**Критерии за верен отговор:**
- Calls log_expense once
- amount = 8.0
- category is Food
- transaction_date = 2026-06-02 (yesterday)

### `track-log-exercise-001`

**Съобщение на потребителя:**

> Log a 30 minute cardio run for today.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_exercise` — `exercise_name` = Running; `category` = Cardio; `workout_date` = 2026-06-03; `duration_minutes` = 30
- **Ефект върху БД:** +1 тренировка

**Еталонен отговор:** Logs a 30-minute cardio running workout dated 2026-06-03.

**Критерии за верен отговор:**
- Calls log_exercise once
- category is Cardio
- duration_minutes = 30
- workout_date = 2026-06-03 (today)

### `track-spending-summary-001`

**Съобщение на потребителя:**

> How much did I spend on Food this week?

**Предварително заредени данни:**
- Разход: 10.0 BGN, Food („Lunch“) на 2026-06-01
- Разход: 15.0 BGN, Food („Groceries“) на 2026-06-03
- Разход: 40.0 BGN, Fitness („Gym shoes“) на 2026-06-02

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `get_spending_summary` — `start_date` = 2026-06-01; `end_date` = 2026-06-03
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Reports that 25 BGN was spent on Food this week (10 + 15), querying the 2026-06-01..2026-06-03 range. Does not modify any data.

**Критерии за верен отговор:**
- Reads spending for the 2026-06-01..2026-06-03 range
- Reports Food total of 25 BGN
- Does not write to the database

### `track-get-expenses-001`

**Съобщение на потребителя:**

> Show me all my Fitness expenses this week.

**Предварително заредени данни:**
- Разход: 40.0 BGN, Fitness („Gym shoes“) на 2026-06-02
- Разход: 12.5 BGN, Fitness („Protein shake“) на 2026-06-03
- Разход: 10.0 BGN, Food („Lunch“) на 2026-06-01

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `get_expenses` — `start_date` = 2026-06-01; `end_date` = 2026-06-03; `category` = Fitness
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Lists the two Fitness expenses in the 2026-06-01..2026-06-03 range (gym shoes 40, protein shake 12.50). Read-only.

**Критерии за верен отговор:**
- Calls get_expenses with category Fitness
- Range is 2026-06-01..2026-06-03
- Returns the two Fitness items, not the Food one
- No write

### `track-relog-expense-001`

**Съобщение на потребителя:**

> I logged my lunch as 10 BGN but it was actually 14. Delete the old one and add the corrected amount.

**Предварително заредени данни:**
- Разход: 10.0 BGN, Food („Lunch“) на 2026-06-03

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `delete_expense` — `expense_id` = <ref:wrong_lunch>
    2. `log_expense` — `amount` = 14.0; `category` = Food; `description` = Lunch; `transaction_date` = 2026-06-03
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Deletes the incorrect 10 BGN lunch expense and logs a corrected 14 BGN Food lunch expense for 2026-06-03.

**Критерии за верен отговор:**
- Deletes the wrong expense by its id
- Logs a new expense with amount 14.0
- category stays Food, date stays 2026-06-03


---

## RAG — въпроси към качени документи

### `rag-factual-protein-001`

**Съобщение на потребителя:**

> What is my daily protein target on training days according to my documents?

**Предварително заредени данни:**
- Документ `nutrition_guidelines.txt`: "Daily protein target: Aim for 1.6 grams of protein per kilogram of body weight on training days. Hydration: drink at least 2.5 litres of water per day. Recommended weekly training volume: at least 150 minutes of moderate…"

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `search_documents`
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** States the protein target is 1.6 grams per kilogram of body weight on training days, grounded in the nutrition document.

**Критерии за верен отговор:**
- Searches the documents
- Answer is 1.6 g protein per kg body weight
- Mentions training days
- Grounded in the document, not invented

### `rag-factual-hydration-001`

**Съобщение на потребителя:**

> How much water should I drink per day based on my nutrition document?

**Предварително заредени данни:**
- Документ `nutrition_guidelines.txt`: "Hydration: Drink at least 2.5 litres of water per day. Add 500 ml for every hour of intense exercise."

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `search_documents`
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** States at least 2.5 litres per day, plus 500 ml per hour of intense exercise, grounded in the document.

**Критерии за верен отговор:**
- Searches the documents
- Answer is at least 2.5 litres per day
- May mention +500 ml per hour of exercise

### `rag-summarise-001`

**Съобщение на потребителя:**

> Summarise the gym membership tiers from my documents.

**Предварително заредени данни:**
- Документ `gym_membership.txt`: "Membership tiers: Basic 35 BGN per month (weights area only); Standard 55 BGN per month (adds group classes and swimming pool); Premium 85 BGN per month (adds a monthly personal trainer session)."

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `get_file_summary` — `file_id` = <ref:gym_doc>
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Summarises the three tiers: Basic 35, Standard 55, Premium 85 BGN/month, with their respective benefits. Grounded in the gym document.

**Критерии за верен отговор:**
- Reads the file via get_file_summary
- Lists Basic 35, Standard 55, Premium 85
- Associates tiers with their benefits

### `rag-factual-cancellation-001`

**Съобщение на потребителя:**

> How much notice do I need to give to cancel my gym membership?

**Предварително заредени данни:**
- Документ `gym_membership.txt`: "Cancellation policy: Memberships can be cancelled with 30 days written notice. No cancellation fee applies after the first 3 months."

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `search_documents`
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** States 30 days written notice are required to cancel, grounded in the gym document.

**Критерии за верен отговор:**
- Searches the documents
- Answer is 30 days written notice

### `rag-not-in-document-001`

**Съобщение на потребителя:**

> Does my gym offer a student discount? Check my documents.

**Предварително заредени данни:**
- Документ `gym_membership.txt`: "Membership tiers: Basic 35, Standard 55, Premium 85 BGN per month. Cancellation requires 30 days written notice. This document does NOT mention any student discount or any free trial period."

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `search_documents`
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Reports that the document does not mention any student discount and does NOT invent one.

**Критерии за верен отговор:**
- Searches the documents
- Says the document does not contain student-discount information
- Does NOT fabricate a discount or percentage


---

## Общи въпроси (без инструменти)

### `general-greeting-001`

**Съобщение на потребителя:**

> Hey there! How are you doing today?

**Очаквано поведение:**

- **Маршрут (route):** general (общ разговор)
- **Очаквани извиквания на инструменти:** няма
- **Забранени инструменти:** всякакъв запис/заявка (11 инструмента) — всяко извикване е провал.
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Responds with a friendly greeting and offers to help. No tools used.

**Критерии за верен отговор:**
- Friendly conversational reply
- No tool calls
- May offer to help with tracking or documents

### `general-definition-001`

**Съобщение на потребителя:**

> What does the term 'progressive overload' mean in strength training?

**Очаквано поведение:**

- **Маршрут (route):** general (общ разговор)
- **Очаквани извиквания на инструменти:** няма
- **Забранени инструменти:** всякакъв запис/заявка (11 инструмента) — всяко извикване е провал.
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Explains progressive overload as gradually increasing training stress (weight, reps, or volume) over time. General knowledge, no tools.

**Критерии за верен отговор:**
- Defines progressive overload correctly
- No tool calls

### `general-explanation-001`

**Съобщение на потребителя:**

> Can you explain the difference between aerobic and anaerobic exercise?

**Очаквано поведение:**

- **Маршрут (route):** general (общ разговор)
- **Очаквани извиквания на инструменти:** няма
- **Забранени инструменти:** всякакъв запис/заявка (11 инструмента) — всяко извикване е провал.
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Explains aerobic (with oxygen, endurance) vs anaerobic (short, intense, without sustained oxygen) exercise. No tools.

**Критерии за верен отговор:**
- Distinguishes aerobic vs anaerobic correctly
- No tool calls

### `general-followup-001`

**Съобщение на потребителя:**

> And what is considered a healthy range?

**Контекст от предходния разговор:**
- *user:* Can you explain what BMI is?
- *assistant:* BMI (Body Mass Index) is weight in kg divided by height in metres squared.

**Очаквано поведение:**

- **Маршрут (route):** general (общ разговор)
- **Очаквани извиквания на инструменти:** няма
- **Забранени инструменти:** всякакъв запис/заявка (11 инструмента) — всяко извикване е провал.
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Answers the follow-up that a healthy BMI is roughly 18.5 to 24.9, using conversation context. No tools.

**Критерии за верен отговор:**
- Uses prior turn context (BMI)
- States healthy range approx 18.5-24.9
- No tool calls

### `general-capability-001`

**Съобщение на потребителя:**

> What kinds of things can you help me with?

**Очаквано поведение:**

- **Маршрут (route):** general (общ разговор)
- **Очаквани извиквания на инструменти:** няма
- **Забранени инструменти:** всякакъв запис/заявка (11 инструмента) — всяко извикване е провал.
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Describes its capabilities (tracking expenses and workouts, answering questions about uploaded documents, general Q&A). No tools.

**Критерии за верен отговор:**
- Describes capabilities at a high level
- No tool calls


---

## Многодомейнни (комбинирани) задачи

### `multi-expense-and-summary-001`

**Съобщение на потребителя:**

> Log that I spent 25 BGN on food today and show me how much I've spent on restaurants this week.

**Предварително заредени данни:**
- Разход: 30.0 BGN, Food („Restaurant dinner“) на 2026-06-01

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_expense` — `amount` = 25.0; `category` = Food; `transaction_date` = 2026-06-03
    2. `get_spending_summary` — `start_date` = 2026-06-01; `end_date` = 2026-06-03
- **Ефект върху БД:** +1 разход

**Еталонен отговор:** First logs a 25 BGN Food expense for today, then reports this week's food/restaurant spending (the new 25 plus the seeded 30 = 55 BGN) over 2026-06-01..2026-06-03.

**Критерии за верен отговор:**
- Logs the 25 BGN Food expense for 2026-06-03 first
- Then queries spending for the week range
- Reports the food/restaurant total including the new entry

### `multi-workout-and-compare-001`

**Съобщение на потребителя:**

> Add a 45-minute running workout and tell me whether I trained more this week than last.

**Предварително заредени данни:**
- Тренировка: Running / Cardio, 30 мин на 2026-05-26
- Тренировка: Cycling / Cardio, 20 мин на 2026-06-02

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_exercise` — `exercise_name` = Running; `category` = Cardio; `workout_date` = 2026-06-03; `duration_minutes` = 45
    2. `get_workout_summary` — `start_date` = 2026-06-01; `end_date` = 2026-06-03
    3. `get_workout_summary` — `start_date` = 2026-05-25; `end_date` = 2026-05-31
- **Ефект върху БД:** +1 тренировка

**Еталонен отговор:** Logs a 45-minute running workout for today, then compares this week's total duration (20 seeded + 45 new = 65 min) against last week's (30 min) and reports that this week is more.

**Критерии за верен отговор:**
- Logs the 45-minute Running cardio workout first
- Queries this-week and last-week ranges
- Concludes this week > last week

### `multi-rag-and-workouts-001`

**Съобщение на потребителя:**

> Find the nutrition recommendations in my documents and compare them with my workouts from the last 7 days.

**Предварително заредени данни:**
- Тренировка: Running / Cardio, 40 мин на 2026-05-29
- Тренировка: Cycling / Cardio, 50 мин на 2026-06-01
- Документ `nutrition_guidelines.txt`: "Recommended weekly training volume: at least 150 minutes of moderate cardio per week, split across at least three sessions."

**Очаквано поведение:**

- **Маршрут (route):** rag (документи)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `search_documents`
    2. `get_workouts` — `start_date` = 2026-05-28; `end_date` = 2026-06-03
- **Само четене** — не трябва да се променя базата данни.

**Еталонен отговор:** Retrieves the recommendation of at least 150 minutes of cardio per week, reads the last-7-days workouts (40 + 50 = 90 minutes), and notes the user is below the recommended volume.

**Критерии за верен отговор:**
- Searches the documents for the recommendation (150 min/week)
- Reads workouts for 2026-05-27..2026-06-03
- Compares actual (90 min) against the recommendation
- No write

### `multi-expense-and-workout-001`

**Съобщение на потребителя:**

> Log 60 BGN for new running shoes today under Fitness, and log a 5 km run for today too.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `log_expense` — `amount` = 60.0; `category` = Fitness; `description` = Running shoes; `transaction_date` = 2026-06-03
    2. `log_exercise` — `exercise_name` = Running; `category` = Cardio; `workout_date` = 2026-06-03; `distance_km` = 5.0
- **Ефект върху БД:** +1 разход, +1 тренировка

**Еталонен отговор:** Logs a 60 BGN Fitness expense for running shoes and a 5 km running workout, both dated 2026-06-03.

**Критерии за верен отговор:**
- Logs the 60 BGN Fitness expense
- Logs a 5 km running workout
- Both dated today (2026-06-03)

### `multi-summary-both-domains-001`

**Съобщение на потребителя:**

> Give me a quick recap of this week: how much I spent in total and how long I worked out.

**Предварително заредени данни:**
- Разход: 20.0 BGN, Food („Groceries“) на 2026-06-02
- Тренировка: Running / Cardio, 35 мин на 2026-06-02

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти (в този ред):**
    1. `get_spending_summary` — `start_date` = 2026-06-01; `end_date` = 2026-06-03
    2. `get_workout_summary` — `start_date` = 2026-06-01; `end_date` = 2026-06-03
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Reports this week's total spending (20 BGN) and total workout duration (35 minutes), both over 2026-06-01..2026-06-03. Read-only.

**Критерии за верен отговор:**
- Queries spending summary for the week
- Queries workout summary for the week
- Reports both totals
- No write


---

## Двусмислени / гранични случаи

### `ambiguous-missing-category-001`

**Съобщение на потребителя:**

> Log 20 BGN for yesterday.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти:** няма
- ➤ Агентът трябва да **зададе уточняващ въпрос**, вместо да гадае.
- **Забранени инструменти:** `log_expense`
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Asks the user which category the 20 BGN expense belongs to before logging anything. Does not write.

**Критерии за верен отговор:**
- Recognises the category is missing
- Asks a clarifying question for the category
- Does NOT call log_expense

### `ambiguous-missing-exercise-001`

**Съобщение на потребителя:**

> Log a workout, 1 hour.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти:** няма
- ➤ Агентът трябва да **зададе уточняващ въпрос**, вместо да гадае.
- **Забранени инструменти:** `log_exercise`
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** тренировките остават непроменени

**Еталонен отговор:** Asks what type of exercise / which movement to log (duration alone is not enough). Does not write.

**Критерии за верен отговор:**
- Recognises the exercise type/name is missing
- Asks a clarifying question
- Does NOT call log_exercise

### `ambiguous-delete-last-001`

**Съобщение на потребителя:**

> Delete my last expense.

**Предварително заредени данни:**
- Разход: 18.0 BGN, Food („Takeaway“) на 2026-06-03

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти:** няма
- ➤ Агентът трябва да **поиска потвърждение** преди да изпълни действието.
- **Забранени инструменти:** `delete_expense`
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** The agent must NOT delete without explicit user confirmation. It MAY read/identify the last expense first (the 18 BGN Food takeaway), but it must ask the user to confirm before deleting and must NOT delete in this turn.

**Критерии за верен отговор:**
- Does NOT call delete_expense without confirmation
- Asks the user to confirm the deletion
- The seeded expense remains in the database

### `ambiguous-period-coffee-001`

**Съобщение на потребителя:**

> How much have I spent on coffee?

**Предварително заредени данни:**
- Разход: 4.0 BGN, Food („Coffee“) на 2026-05-20
- Разход: 4.5 BGN, Food („Coffee“) на 2026-06-02

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти:** няма
- ➤ Агентът трябва да **зададе уточняващ въпрос**, вместо да гадае.
- **Забранени инструменти:** `get_expenses`, `get_spending_summary`
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени

**Еталонен отговор:** Asks which time period to consider (no period was specified) before reporting a coffee total. Does not hallucinate a number.

**Критерии за верен отговор:**
- Recognises the time period is unspecified
- Asks which period to use (or states an explicit assumed period)
- Does NOT invent a coffee total

### `ambiguous-vague-good-day-001`

**Съобщение на потребителя:**

> Track that I had a good day.

**Очаквано поведение:**

- **Маршрут (route):** tracking (проследяване)
- **Очаквани извиквания на инструменти:** няма
- ➤ Агентът трябва да **зададе уточняващ въпрос**, вместо да гадае.
- **Забранени инструменти:** `log_expense`, `log_exercise`
- **Само четене** — не трябва да се променя базата данни.
- **Ефект върху БД:** разходите остават непроменени, тренировките остават непроменени

**Еталонен отговор:** Asks what specifically to track (an expense, a workout, etc.), since the request has no loggable detail. Does not write.

**Критерии за верен отговор:**
- Recognises there is nothing concrete to log
- Asks the user to specify what to track
- Does NOT call any write tool
