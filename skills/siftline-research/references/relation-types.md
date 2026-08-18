# Relation Types

Use multiple relation types because topical similarity is only one weak path.

| Relation | Question | Typical value |
| --- | --- | --- |
| lexical | Uses the same terms | Finds obvious neighbors; low novelty |
| problem | Addresses the same user/player job under different language | Reveals competitors and hidden demand |
| mechanism | Uses the same causal mechanism | Finds structurally similar work across domains |
| experience | Produces the same desired feeling or workflow | Useful when implementation differs |
| origin | Earlier theory, citation, author, or predecessor | Explains where the idea came from |
| descendant | Later implementation, product, game, or research | Tests whether the idea survived contact with reality |
| component | Implements one important submechanic | Reveals reusable patterns and missing dependencies |
| combination | Becomes useful when joined with another idea | Generates non-obvious product or design directions |
| demand | Shows users or players paying a cost for the outcome | Tests whether interest is consequential |
| failure | Shows why a similar attempt failed | Exposes constraints hidden by success stories |
| counterexample | Contradicts the seed's causal story | Prevents premature convergence |
| boundary | Works only for a different audience, scale, or context | Defines where the analogy stops |

For every retained source, label one primary relation and explain the bridge in one sentence. Do not call two items related merely because embeddings or keywords are close.

Each retained source carries the entailment fields from evidence-integrity §2.1 (or a compact equivalent: `source_url`, `exact_observed_content`, `proposed_claim`, `primary_relation`, `entailment=direct|analogue-only|unsupported`, `maximum_allowed_wording`, `does_not_support`). Analogue, component, and attention evidence are their own buckets and never masquerade as demand. A candidate is not a "successful neighbor" without direct adoption/outcome evidence; otherwise label it `analogue` or `candidate`.

Prioritize relations by expected decision impact:

1. demand, failure, counterexample, boundary;
2. mechanism, problem, descendant;
3. origin, component, combination;
4. lexical.

Change the order when the user's goal is inspiration rather than validation.
