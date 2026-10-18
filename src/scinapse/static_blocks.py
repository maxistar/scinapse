"""Static document blocks: schema version, assessment policy, graph view.

Copied from sample_response.json ("1.1") with demo provenance replaced by real
tokens and the edge-display rules rewritten for the 3-type edge contract
(``citation_overlap`` / ``shared_author`` / ``similar_to``), each carrying one
strength value in [0,1]; category priority: shared_author > citation_overlap >
similar_to.
"""

SCHEMA_VERSION = "1.1"

ASSESSMENT_POLICY = {
    "relevance_scope": "research_question",
    "strength_comparison": "within_same_metric_and_method_version",
    "confidence_definition": "Confidence that the stated relationship is supported by the inspected evidence.",
    "quality_scoring": "dimension_based",
    "institution_prestige_used_as_quality_score": False,
    "missing_evidence": "unknown_or_not_assessed",
    "relevance_scoring": {
        "method": "weighted_rubric",
        "version": "relevance_v1",
        "range": [0, 1],
        "weights": {
            "research_question_alignment": 0.4,
            "disease_setting_alignment": 0.2,
            "method_alignment": 0.2,
            "outcome_alignment": 0.2,
        },
        "formula": "Round the weighted sum of dimension scores to 2 decimal places.",
        "missing_dimension_policy": "Return a null total if any required dimension is unknown.",
        "assessment_thresholds": {
            "highly_relevant": [0.8, 1.0],
            "potentially_relevant": [0.5, 0.8],
            "indirectly_relevant": [0.2, 0.5],
            "not_relevant": [0.0, 0.2],
        },
        "threshold_interpretation": "Lower bounds inclusive; upper bounds exclusive except 1.0.",
        "interpretation": "Alignment with this research question; not a probability or paper quality score.",
        "provenance": "llm_abstract_rubric_v1",
    },
    "edge_display_scoring": {
        "method": "relationship_priority_v1",
        "range": [0, 1],
        "rules": {
            "citation_overlap": {
                "formula": "max(1.0 when a direct citation record exists, reference_jaccard)",
                "input_metric": "citation_exists_or_reference_jaccard",
            },
            "shared_author": {
                "formula": "strength.value (author_overlap_salton)",
                "input_metric": "author_overlap_salton",
            },
            "similar_to": {
                "formula": "round((raw_cosine + 1) / 2, 4)",
                "input_metric": "abstract_cosine_similarity",
            },
        },
        "interpretation": (
            "UI relationship priority; not scientific strength or confidence. Each edge carries "
            "one strength value in [0,1]; category priority: shared_author > citation_overlap > similar_to."
        ),
        "provenance": "scinapse_local",
    },
}

GRAPH_VIEW = {
    "edge_display": {
        "mode": "strongest_per_node_pair",
        "group_by": "unordered_node_pair",
        "selection_field": "display_score.value",
        "selection_order": "descending",
        "null_scores": "exclude_from_default_selection",
        "tie_breaker": "edge_id_ascending",
        "preserve_selected_edge_direction": True,
        "show_hidden_relationship_count": True,
        "details_panel": "show_all_edges_including_reverse_directions",
        "relationship_filter": "apply_before_selection",
    }
}
