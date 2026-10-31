from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, adjusted_rand_score

# Set folders
from config import folder as default_folder
folder = Path(sys.argv[1]) if len(sys.argv) > 1 else default_folder
output = folder / 'remaining_analysis'
output.mkdir(exist_ok=True)

# Read saved files
def read(name):
    file = folder / name
    if not file.exists():
        file = folder / name.replace('.csv', '(1).csv')
    return pd.read_csv(file)

daily = read('daily_model_summary.csv')
types = read('model_classification.csv')
review = read('all_model_review.csv')
daily['date'] = pd.to_datetime(daily['date'])
if types['model'].duplicated().any() or daily.duplicated(['date', 'model']).any():
    raise SystemExit('Duplicate model labels or daily keys need review.')

# Check totals before adding analysis
data = daily.merge(types[['model', 'drive_type', 'capacity_bytes']], on='model', how='left', validate='many_to_one')
if data['drive_type'].isna().any():
    raise SystemExit('Some daily models have no classification record.')
hdd = data[data['drive_type'] == 'HDD'].copy()
annual = hdd.groupby('model', as_index=False).agg(
    flags=('failure_flag_rows', 'sum'), drive_days=('drive_days', 'sum'),
    observed_days=('date', 'nunique'), average_daily_drives=('observed_drives', 'mean'))
annual = annual.merge(types[['model', 'capacity_bytes']], validate='one_to_one')
annual['afr_percent'] = annual['flags'] * 36500 / annual['drive_days']
check = annual.merge(review[['model', 'annual_failure_flags', 'annual_drive_days']], validate='one_to_one')
if len(check) != len(annual) or not (check['flags'].eq(check['annual_failure_flags']) & check['drive_days'].eq(check['annual_drive_days'])).all():
    raise SystemExit('Saved review and daily totals disagree. Refresh those files first.')
print('\nINPUT CHECK:')
print('Models:', len(types), '| HDD models:', len(annual))
print('All drive-days:', daily['drive_days'].sum(), '| All flags:', daily['failure_flag_rows'].sum())

# Exclude each model from its capacity benchmark
totals = annual.groupby('capacity_bytes')[['flags', 'drive_days']].transform('sum')
annual['other_flags'] = totals['flags'] - annual['flags']
annual['other_drive_days'] = totals['drive_days'] - annual['drive_days']
annual['other_models'] = annual.groupby('capacity_bytes')['model'].transform('size') - 1
annual['peer_afr_percent'] = annual['other_flags'] * 36500 / annual['other_drive_days'].replace(0, np.nan)
annual['rate_ratio'] = annual['afr_percent'] / annual['peer_afr_percent'].replace(0, np.nan)
annual['peer_evidence'] = np.where(annual['other_drive_days'] >= 100000, 'At least 100000 peer drive-days', 'Limited peer exposure')
annual.loc[annual['other_models'] == 0, 'peer_evidence'] = 'No same-capacity peer'

# Compare rates under a common Poisson-rate assumption
annual['p_value'] = np.nan
for index, row in annual.iterrows():
    total_flags = int(row['flags'] + row['other_flags'])
    if row['other_drive_days'] > 0 and total_flags > 0:
        share = row['drive_days'] / (row['drive_days'] + row['other_drive_days'])
        annual.loc[index, 'p_value'] = binomtest(int(row['flags']), total_flags, share).pvalue

# Adjust for testing several models
ordered = annual['p_value'].dropna().sort_values()
adjusted = np.maximum.accumulate(ordered.to_numpy() * np.arange(len(ordered), 0, -1)).clip(0, 1)
annual['holm_p_value'] = pd.Series(adjusted, index=ordered.index)
annual['elevated_after_holm'] = (annual['afr_percent'] > annual['peer_afr_percent']) & (annual['holm_p_value'] < 0.05)
annual.to_csv(output / 'independent_capacity_peers.csv', index=False)
print('\nABOVE SAME-CAPACITY PEERS AFTER HOLM ADJUSTMENT:')
print(annual.loc[annual['elevated_after_holm'], ['model', 'afr_percent', 'peer_afr_percent', 'other_drive_days', 'holm_p_value']].round(4).to_string(index=False))
print('These comparisons are not adjusted for age, role, workload or operational events.')

# Build monthly pattern features
hdd['month'] = hdd['date'].dt.to_period('M').astype(str)
monthly = hdd.groupby(['model', 'month'], as_index=False).agg(flags=('failure_flag_rows', 'sum'), drive_days=('drive_days', 'sum'))
monthly['afr_percent'] = monthly['flags'] * 36500 / monthly['drive_days']
variation = monthly.groupby('model')['afr_percent'].agg(['mean', 'std'])
variation['monthly_rate_cv'] = variation['std'] / variation['mean'].replace(0, np.nan)
features = annual.merge(variation[['monthly_rate_cv']], left_on='model', right_index=True, validate='one_to_one')
features.loc[features['flags'] == 0, 'monthly_rate_cv'] = 0
features['log_rate'] = np.log1p(features['afr_percent'])
features['log_fleet'] = np.log1p(features['average_daily_drives'])
features['log_variation'] = np.log1p(features['monthly_rate_cv'])
columns = ['log_rate', 'log_fleet', 'log_variation']

# Compare cluster counts and random starting points
def cluster(table):
    scaled = StandardScaler().fit_transform(table[columns])
    scores = []
    for k in range(2, min(5, len(table) - 1) + 1):
        labels = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(scaled)
        scores.append({'k': k, 'silhouette': silhouette_score(scaled, labels)})
    scores = pd.DataFrame(scores)
    k = int(scores.sort_values('silhouette', ascending=False).iloc[0]['k'])
    labels = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(scaled)
    stability = []
    for seed in range(10):
        other = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(scaled)
        stability.append(adjusted_rand_score(labels, other))
    return labels, scores, min(stability)

eligible = features[(features['observed_days'] >= 180) & (features['drive_days'] >= 100000)].dropna(subset=columns).copy()
if len(eligible) < 7:
    raise SystemExit('Too few eligible models for the clustering comparison.')
labels, scores, stability = cluster(eligible)
eligible['cluster'] = labels + 1
scores.to_csv(output / 'cluster_count_check.csv', index=False)
eligible.to_csv(output / 'model_clusters.csv', index=False)
summary = eligible.groupby('cluster').agg(models=('model', 'size'), median_afr_percent=('afr_percent', 'median'), median_daily_drives=('average_daily_drives', 'median'), median_monthly_cv=('monthly_rate_cv', 'median'))
summary.to_csv(output / 'cluster_summary.csv')
print('\nEXPLORATORY CLUSTERS:')
print(scores.round(3).to_string(index=False))
print(summary.round(3).to_string())
print('Lowest agreement across 10 random starts:', round(stability, 3))

# Check whether eligibility changes the groups
sensitivity = []
for threshold in [50000, 100000, 200000]:
    subset = features[(features['observed_days'] >= 180) & (features['drive_days'] >= threshold)].dropna(subset=columns).copy()
    if len(subset) < 7:
        continue
    labels, tested, stable = cluster(subset)
    subset['alternative_cluster'] = labels
    common = eligible[['model', 'cluster']].merge(subset[['model', 'alternative_cluster']], on='model')
    sensitivity.append({'minimum_drive_days': threshold, 'models': len(subset), 'selected_k': int(tested.loc[tested['silhouette'].idxmax(), 'k']), 'agreement_on_shared_models': adjusted_rand_score(common['cluster'], common['alternative_cluster']), 'minimum_seed_agreement': stable})
pd.DataFrame(sensitivity).to_csv(output / 'cluster_sensitivity.csv', index=False)
print('\nCLUSTER ELIGIBILITY CHECK:')
print(pd.DataFrame(sensitivity).round(3).to_string(index=False))

# Follow the saved July starting cohort
start = read('toshiba_july_start.csv')
records = read('toshiba_location_records.csv')
start['serial_number'] = start['serial_number'].astype('string').str.strip()
records['serial_number'] = records['serial_number'].astype('string').str.strip()
records['date'] = pd.to_datetime(records['date'])
if start['serial_number'].duplicated().any() or records.duplicated(['date', 'serial_number']).any():
    raise SystemExit('Duplicate serial keys in the Toshiba files need review.')
start['smart_9_raw'] = pd.to_numeric(start['smart_9_raw'], errors='coerce')
start = start[start['smart_9_raw'].ge(0)].copy()
start['raw_band'] = pd.qcut(start['smart_9_raw'], 3, duplicates='drop').astype(str)
start = start.rename(columns={'vault_id': 'baseline_vault'})
period = records[records['date'].between('2025-07-01', '2025-10-31')].merge(start[['serial_number', 'baseline_vault', 'raw_band']], on='serial_number', validate='many_to_one')
first_flag = period[period['failure'] == 1].groupby('serial_number')['date'].min()
period['first_flag_date'] = period['serial_number'].map(first_flag)
period['after_first_flag'] = period['date'] > period['first_flag_date']
followup = period[~period['after_first_flag']].copy()
cohort = start.merge(first_flag.rename('first_flag_date'), on='serial_number', how='left', validate='one_to_one')
cohort['flagged'] = cohort['first_flag_date'].notna().astype(int)
age = cohort.groupby(['baseline_vault', 'raw_band'], observed=True).agg(baseline_drives=('serial_number', 'size'), flagged_drives=('flagged', 'sum')).reset_index()
exposure = followup.groupby(['baseline_vault', 'raw_band']).size().rename('observed_drive_days').reset_index()
age = age.merge(exposure, how='left', validate='one_to_one')
age['flagged_share_percent'] = age['flagged_drives'] / age['baseline_drives'] * 100
age.to_csv(output / 'toshiba_baseline_raw_bands.csv', index=False)
cohort.to_csv(output / 'toshiba_baseline_cohort.csv', index=False)
print('\nTOSHIBA JULY COHORT BY BASELINE SMART 9 RAW BAND:')
print(age.round(3).to_string(index=False))
print('Raw bands are relative readings, not verified ages in years.')
print('Flagged share covers this fixed starting cohort. Missing records are not proof of survival.')

# Record what is still unsupported
limits = pd.DataFrame([
    ['Drive role', 'Unresolved', 'HDD type does not establish boot or storage role.'],
    ['Workload', 'Unresolved', 'Capacity and drive-days do not measure read/write activity.'],
    ['Whole-fleet age adjustment', 'Not possible from uploaded summaries', 'Only one model and four vaults have baseline SMART readings. Raw units need verification.'],
    ['Clustering', 'Exploratory analysis completed', 'Eligibility and feature choices affect groups. Cluster labels do not establish reliability or cause.'],
    ['Capacity tests', 'Unadjusted comparisons completed', 'Poisson assumptions and dependent peer tests limit interpretation. Holm controls multiple testing under valid individual tests.'],
    ['Toshiba cohort', 'Relative raw-reading analysis completed', 'Selected baseline survivors, missing follow-up and maintenance flags prevent a mechanical-failure or causal interpretation.']
], columns=['topic', 'status', 'evidence_limit'])
limits.to_csv(output / 'analysis_evidence_limits.csv', index=False)

# Attach new evidence without replacing the saved shortlist
updated = review.merge(eligible[['model', 'cluster']], on='model', how='left', validate='one_to_one')
updated = updated.merge(annual[['model', 'peer_afr_percent', 'other_drive_days', 'holm_p_value', 'elevated_after_holm', 'peer_evidence']], on='model', how='left', validate='one_to_one')
updated['cluster_status'] = np.where(updated['cluster'].isna(), 'Below eligibility rule', 'Exploratory group')
updated.to_csv(output / 'review_with_additional_evidence.csv', index=False)
print('\nSaved new results in:', output)
print('Existing results were not overwritten. Review cluster sensitivity and evidence limits before updating Power BI.')
