# Codex Academy - Product Requirements, Architecture, and Workflow Documentation

This document contains:

1. Full PRD
2. Claude + Cursor hybrid workflow guide
3. Reserved section for UI/UX layout planning

---

# 1. PRODUCT REQUIREMENTS DOCUMENT (PRD)

## Vision

To restore true learning in an AI-saturated world by transforming human-created educational content into structured, multi-source, verifiable courses—using AI only as an assistant, not a replacement for thinking.

## Problem

People increasingly rely on AI to do the thinking for them. This leads to shallow understanding, hallucinations, lack of multi-source validation, and deteriorating reasoning skills. Existing educational tools are limited in scope, static, or require intensive human curation.

## Product Summary

Codex Academy automatically constructs learning experiences from real-world sources such as YouTube videos and web articles. It extracts transcript and visual information, merges and verifies claims, and builds structured, adaptive, visually-informed courses.

AI acts as a curator and organizer—not as a teacher.

## Target Users

* Curious lifelong learners
* Students
* Hobbyists and jack-of-all-trades personalities
* Professionals exploring new domains

## Goals

1. Automatically construct structured, multi-source courses.
2. Preserve cognitive effort while eliminating noise.
3. Base all information on human-created content.
4. Adapt visual intelligence based on topic.
5. Integrate meaningful gamification.
6. Provide a domain-limited assistant.

## Key Features

### Knowledge Collection Layer

* YouTube transcript extraction
* Article retrieval
* Visual Tier Classification (VCT 1–5)
* Vision analysis (slides, diagrams, OCR)

### Knowledge Extraction Layer

* Claim triples (transcript + visual)
* Contradiction detection
* Consensus modeling

### Course Construction

* Overview, fundamentals, visuals, examples, troubleshooting, glossary, quizzes

### UX & Gamification

* XP system
* Badges (including "First Explorer")
* Depth and breadth mastery
* Skill trees

### Domain-Limited Chatbot

* Answers ONLY based on course content
* No hallucinations
* cites course sections

## Non-Goals

* Not a general chatbot
* Not AI-generated knowledge
* Not meant to replace teachers

## Tech Stack

* Python + FastAPI
* Ollama (Mixtral, LLaVA, Embedding Models)
* ffmpeg + yt-dlp
* SQLite caching
* Next.js frontend

## KPIs

* Course completion rates
* Chunk extraction accuracy
* VCT success
* Chatbot correctness
* User exploration metrics

## Roadmap

### Phase 1 – MVP

* Query input
* Multi-source gathering
* Basic synthesis
* Domain-limited assistant

### Phase 2 – Vision Intelligence

* VCT tiers
* Frame analysis
* Visual claims

### Phase 3 – Gamification

* XP, badges, mastery paths

### Phase 4 – Full Course Ecosystem

* Quizzes, learning paths, skill trees

---

# 2. CLAUDE + CURSOR HYBRID WORKFLOW GUIDE

## Roles

Claude → Architect, planner, systems designer.
Cursor → Coder, builder, debugger.

## Workflow

1. Use Claude for system architecture, data flow, API design, and prompts.
2. Move Claude's output into Cursor for implementation.
3. Cursor writes modules, endpoints, components, and refactors.
4. Test locally.
5. Return to Claude for improvements and reasoning-heavy tasks.
6. Iterate.

## Best Practices

* Claude handles complex thinking.
* Cursor handles code creation and editing.
* Keep Claude focused on design; Cursor on execution.
* Always give Cursor specific file-level instructions.
* Use PRDs and architecture docs as shared context.

---

# 3. UI/UX LAYOUT (UPDATED WITH MOCKUP GUIDANCE)

Based on provided mockups, Seikna’s UI/UX direction is confirmed as the **Hybrid Model**: clean, modern, structured, with light gamification.

---

## **A. Design Principles**

* Minimalist, modern, trustworthy visual language
* Strong emphasis on structure and readability
* Intelligent use of dark/light modes
* Motivational UI without distraction
* Consistent spacing, typography hierarchy, and iconography

---

## **B. Core Screens & Layout Specifications**

### **1. Home / Landing Page**

**Purpose:** Introduce users to Seikna, motivate exploration, and guide them into learning paths.

**Key UI regions:**

* **Header:** logo, profile, streak, XP indicator
* **Hero search bar:** centered, large, inviting
* **Suggested Topics Section:** card grid, grouped categories
* **Recently Viewed:** horizontally scrollable row
* **Subtle gamification preview:** streak count, badges, XP

**Design notes from mockup:**

* Dark gradient background for hero area
* Soft glows and elevated cards for modern feel

---

### **2. Search Results Page**

**Purpose:** Provide quick scan-ability with verified source indicators.

**Key UI elements:**

* Topic result cards featuring:

  * Difficulty level
  * Visual Tier
  * Source count (videos + articles)
  * Short description

**Layout:** 2–3 column grid, top filter bar, left-aligned titles.

---

### **3. Course Overview Page**

**Purpose:** Show structure of the learning path.

**Sections:**

* Title + short description
* Syllabus (collapsible lessons)
* Right panel with insights:

  * Prerequisites
  * Time estimate
  * Key sources & contributors

**Styling cues:**

* Clean white or light-mode panel with subtle borders
* Strong left alignment for syllabus tree

---

### **4. Module Lesson Page**

**Purpose:** Deep reading & visual understanding.

**Key UI pieces:**

* Left navigation (modules + submodules)
* Central article viewer with:

  * Diagrams
  * Key verified facts
  * Interactive checkpoints
* “Checkpoint” CTA at bottom for progression

**Notes:**

* Verified facts styled as green-highlight blocks
* Visuals centered, with captions + source citations

---

### **5. Domain-Limited Chatbot Panel**

**Purpose:** Contextual support using only course data.

**UI design:**

* Slide-out right panel with:

  * Chat history
  * Reference links
  * Source citations inside bubbles

**Key behavior:**

* Always references specific course sections
* Mentions “verified fact” when relevant

---

### **6. User Profile / Gamification Dashboard**

**Purpose:** Motivate ongoing learning.

**UI components:**

* Knowledge graph visualization (multi-domain tree)
* Statistics: deep work hours, streak, badges
* Explorer badges panel

**Aesthetic markers:**

* Neon lines for the knowledge tree
* Minimalistic badge icons

---

## **C. Component Library (Initial)**

* Cards (topic, course, badge)
* Navigation sidebar
* Hero search bar
* Syllabus accordion
* Chat panel
* XP progress bar
* Knowledge tree visualization widget

---

## **D. Interaction Flow**

1. User searches → sees structured results.
2. User selects topic → enters course overview.
3. User starts lesson → reads modules sequentially.
4. Chatbot assists with grounded responses.
5. User unlocks checkpoints → earns XP.
6. Profile dashboard reflects progress.

---

## **E. Responsive Behavior**

* Mobile collapses left nav into drawer
* Chatbot becomes bottom sheet on mobile
* Course modules stack vertically

---

UI/UX section updated to match mockups and product direction.
