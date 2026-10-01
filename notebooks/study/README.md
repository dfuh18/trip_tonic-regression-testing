# Study notebooks 05-09. Outputs are stripped by the nbstripout filter
# configured in .gitattributes here. Never commit a notebook with output cells:
# they hold participant rows and git history is permanent.
#
#   05_pilot                 pilot flow check (C01); RUN_TYPE switches to "study" for C06
#   05c_study_check          05_pilot on the study cohort (C06 and checks during the round)
#   05b_pilot_shapes         request-shape rules on the pilot turns (evidence for D99/D100)
#   06_analysis              the propositions, dry run on the pilot (C02)
#   07_pilot_distributions   basic distribution figures, pilot
#   08_study_distributions   basic distribution figures, participant round (run after it closes)
#   09_study_propositions    the propositions, participant round (run after C03)
#
# 06/09 and 07/08 are the same notebook with a different RUN_TYPE. The logic is
# in src/analysis.py and src/pilot.py, the figures in src/figures.py; change it
# there, not in one copy. Figures are written to figures/<run_type>/, which is
# git-ignored.
