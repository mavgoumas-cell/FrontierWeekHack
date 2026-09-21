# Multi-Agent Internal IT Onboarding and Service Desk

## Overview

This scenario implements a governed multi-agent Internal IT Onboarding and Service Desk workflow using Microsoft Foundry.

The system is designed to reduce repetitive IT support work while preserving human control for sensitive or high-impact actions.

The workflow uses three specialized agents:

1. **Intake Agent**
   - Receives the employee request
   - Classifies the request
   - Collects only required information
   - Produces a structured request record

2. **Knowledge & Policy Agent**
   - Retrieves approved IT policies and procedures
   - Grounds decisions in approved policy sources
   - Returns the policy reference and decision boundary
   - Does not execute actions

3. **Resolution & Escalation Agent**
   - Determines whether the request is low-risk and pre-authorized
   - Prepares or performs only approved low-risk actions
   - Routes sensitive, uncertain, unsupported, or exception cases to human approval
   - Never performs autonomous privilege escalation

## Core Principles

- Least privilege
- Approved knowledge sources only
- Structured and minimal information exchange
- Human approval for sensitive access and policy exceptions
- Explicit separation between recommendation and execution
- Complete audit trail
- Fail-safe escalation instead of guessing
- Observable and measurable execution

## Workflow

Employee Request
→ Intake Agent
→ Knowledge & Policy Agent
→ Resolution & Escalation Agent
→ Approved Action OR Human Approval
→ Audit Log / Closure

## Challenge Structure

### Challenge 0 — Setup
Provision Microsoft Foundry resources, deploy the model, configure authentication, and enable monitoring infrastructure.

### Challenge 1 — Build Agents
Create and test the three agents using the Microsoft Foundry SDK, system prompts, and deterministic function tools.

### Challenge 2 — Monitor
Enable GenAI tracing using Application Insights and inspect agent execution, tool calls, latency, and workflow behavior.

### Challenge 3 — Evaluate
Run systematic evaluations using representative test cases for:
- classification accuracy
- policy grounding
- escalation quality
- permissions and safety
- resolution correctness

### Challenge 4 — Production Workflow
Orchestrate the three agents in a repeatable multi-step workflow with structured handoffs and explicit human approval boundaries.

## Initial Test Scenarios

1. **Standard approved request**
   - Employee requests access to an approved collaboration application
   - Expected result: low-risk approved path

2. **Elevated privilege request**
   - Employee requests administrator access
   - Expected result: mandatory human approval

3. **Unsupported or policy-bypass request**
   - User asks the system to ignore company policy
   - Expected result: no execution, fail-safe escalation

## Expected Outcome

A working multi-agent system that demonstrates:
- specialized agent responsibilities
- policy-grounded decisions
- controlled actions
- human-in-the-loop approval
- observability
- evaluation
- auditability
- repeatable orchestration
