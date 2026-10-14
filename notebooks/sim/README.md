# Stage notebooks 01-04. Outputs are committed on purpose: these are the
# worked examples published alongside the thesis.
#
#   00_prompts            the simulator and judge prompts in 01_cases' layout,
#                         for the thesis; reads src/prompts/, needs no database.
#   00_logging_schema     every study_* column and JSON key as dense tables
#                         A.1-A.4 for the appendix; checked against the
#                         migrations, needs no database.
#   04b_regress_summary   stages 3.1 + 3.2 condensed for the report: dense tables
#                         and figures R1-R6 (written to figures/regression/),
#                         read from the stored runs, descriptive only.
#   04c_pooled_summary    the same two runs pooled as one sample (no pair-wise
#                         comparison): judge scores, structural outcomes, turns,
#                         recovered tool errors, latency, cost; figures P1-P3
#                         (written to figures/pooled/).
#   08b_segmentation_pooled  D100's request boundaries (shape + slash, no
#                         reference) on the same two runs pooled: split and
#                         merge error, request count, missed seams by shape;
#                         figures S1-S2 (written to figures/segmentation/).
