import numpy as np
import pandas as pd
import scipy.stats as stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st

#from numpy.random import default_rng
#rng = default_rng(17)
np.random.seed(7)   

def posterior_for_binom_and_uniform_prior(p, n_heads, n_trials):
    alpha_prior = 1
    beta_prior = 1
    alpha_post = alpha_prior + n_heads
    beta_post = beta_prior + (n_trials - n_heads)
    return stats.beta.pdf(p, alpha_post, beta_post)

def hpdi_for_binom_and_uniform_prior(hpdi, n_heads, n_trials):
    #todo: switch to built-in quantile functions?
    p_grid = np.linspace(start=0, stop=1, num=3001)
    p_posterior = np.array([posterior_for_binom_and_uniform_prior(p, n_heads, n_trials) for p in p_grid])
    norm = np.sum(p_posterior)
    n_start = np.argmax(p_posterior)
    n_left = n_start
    n_right = n_start
    s = p_posterior[n_start]
    while s < hpdi * norm:
        next_left = p_posterior[n_left - 1]
        next_right = p_posterior[n_right + 1]
        if next_left > next_right:
            n_left = n_left - 1
            s = s + next_left
        elif next_left < next_right:
            n_right = n_right + 1
            s = s + next_right
        else:
            n_left = n_left - 1
            n_right = n_right + 1
            s = s + next_left + next_right
    return (p_grid[n_left], p_grid[n_right])

def posterior_sample_for_binom_and_uniform_prior(ns, ntotal, n_sample):
    alpha_prior = 1
    beta_prior = 1
    a = alpha_prior + ns
    b = beta_prior + (ntotal - ns) 
    return np.random.beta(a, b, n_sample)

def alpha_beta_post(alpha, beta, n_conv, n_total):
    alpha_post = alpha + n_conv
    beta_post = beta + (n_total - n_conv)
    return alpha_post, beta_post

def beta_post_dist(alpha, beta, n_conv, n_total):
    alpha_post = alpha + n_conv
    beta_post = beta + (n_total - n_conv)
    return stats.beta(a=alpha_post, b=beta_post)

def prob_pb_gt_pa(p_a, p_b, N_a, N_b = None):
    N_b = N_a if N_b is None else N_b
    n_sample = 30000
    post_sample_a = posterior_sample_for_binom_and_uniform_prior(p_a * N_a, N_a, n_sample)
    post_sample_b = posterior_sample_for_binom_and_uniform_prior(p_b * N_b, N_b, n_sample)
    post_sample_diff = post_sample_b - post_sample_a
    prob_b_gt_a = len(post_sample_diff[post_sample_diff > 0]) / len(post_sample_diff)
    return prob_b_gt_a

def pb_ge_pa_sims(s_a, s_b, n_cmp=30000):
    n_pars = len(s_a['alpha_post'])
    pa = stats.beta.rvs(s_a['alpha_post'], s_a['beta_post'], size=(n_cmp, n_pars))
    pb = stats.beta.rvs(s_b['alpha_post'], s_b['beta_post'], size=(n_cmp, n_pars))
    return np.sum(pb >= pa, axis=0) / n_cmp   

def simulate(p, trials, alpha, beta):
    trials_conv = stats.binom.rvs(n=trials, p=p)
    trials_accum = np.cumsum(trials)
    trials_conv_accum = np.cumsum(trials_conv)
    alpha_post = trials_conv_accum + alpha
    beta_post = (trials_accum - trials_conv_accum) + beta
    s = {
        'p': p,
        'trials_accum': trials_accum,
        'trials_conv_accum': trials_conv_accum,
        'alpha_post': alpha_post,
        'beta_post': beta_post
    }
    return s 

def min_days_to_reach_certainty_level(probs_pb_ge_pa, days, required_pb_ge_pa):
    prob_gt_required = (probs_pb_ge_pa > required_pb_ge_pa) | (probs_pb_ge_pa < 1 - required_pb_ge_pa)
    reached = days[prob_gt_required]
    min_reached = np.min(reached) if prob_gt_required[-1] else np.max(days)
    return min_reached
 

def init_conv_session_values():
    if 'conv_a_exact' not in st.session_state:
        st.session_state['conv_a_exact'] = 15.0
    if 'conv_b_exact' not in st.session_state:
        st.session_state['conv_b_exact'] = 16.0
    if 'conv_daily_users' not in st.session_state:
        st.session_state['conv_daily_users'] = 3000
    if 'conv_n_days' not in st.session_state:
        st.session_state['conv_n_days'] = 10
    if 'conv_b_split' not in st.session_state:
        st.session_state['conv_b_split'] = 50.0
    if 'conv_pb_gt_pa_required' not in st.session_state:
        st.session_state['conv_pb_gt_pa_required'] = 95.0
    if 'conv_sim_max_days' not in st.session_state:
        st.session_state['conv_sim_max_days'] = 30
    if 'conv_n_simulations' not in st.session_state:
        st.session_state['conv_n_simulations'] = 100
        
init_conv_session_values()
#st.session_state

st.title('Conversions Comparison')

st.subheader("Generate Data")

col1, col2 = st.columns(2)

with col1:
    st.number_input(label='p_A Exact, %',
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    format='%f',
                    key='conv_a_exact')

with col2:
    st.number_input(label='p_B Exact, %',
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    format='%f',
                    key='conv_b_exact')

st.number_input(label='Daily Users',
                min_value=0,
                step=100,
                format='%d',
                key='conv_daily_users')
st.number_input(label='N Days',
                min_value=0,
                step=1,
                format='%d',
                key='conv_n_days')            
st.number_input(label='B Group Traffic, %',
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format='%f',
                key='conv_b_split')


trials = np.full(fill_value=st.session_state['conv_daily_users'],
                 shape=st.session_state['conv_n_days'])
conv_b_split = st.session_state['conv_b_split'] / 100
a_trials = np.rint(trials * (1 - conv_b_split)).astype(int)
b_trials = np.rint(trials * conv_b_split).astype(int)

conv_a_exact = st.session_state['conv_a_exact'] / 100
conv_b_exact = st.session_state['conv_b_exact'] / 100
a_trials_conv = stats.binom.rvs(n=a_trials, p=conv_a_exact)
b_trials_conv = stats.binom.rvs(n=b_trials, p=conv_b_exact)

df_exp = pd.concat([
    pd.DataFrame({'group': np.full(fill_value='A', shape=len(a_trials)),
                  'day': np.arange(len(a_trials)),
                  'n_users': a_trials,
                  'conv': a_trials_conv}),
    pd.DataFrame({'group': np.full(fill_value='B', shape=len(b_trials)),
                  'day': np.arange(len(b_trials)),
                  'n_users': b_trials,
                  'conv': b_trials_conv})
])
with st.expander("Show Generated Data"):
    st.dataframe(df_exp)

df = df_exp.copy()

st.subheader("Results")

summary_container = st.container()
summary_bar = summary_container.progress(0)

st.subheader("Details")

df_summary = df_exp.groupby(['group'])[['n_users', 'conv']].sum()
df_summary['p'] = df_summary['conv'] / df_summary['n_users']
df_summary['col'] = pd.Series({'A': 'red', 'B':'blue'})

df_formatted = df_summary[[]].copy()
df_formatted['Total Users'] = df_summary['n_users'].astype(str)
df_formatted['Converted Users'] = df_summary['conv'].astype(str)

summary_bar.progress(0.1)
#summary_container.write(df_formatted.T)

df_plot = df_exp.set_index('group')

fig = make_subplots(rows=1, cols=2, 
                    column_widths=[0.85, 0.15],
                    subplot_titles=("Daily", "Total"))
for gr in df_plot.index.unique():
    fig.add_trace(
        go.Scatter(x=df_plot['day'][gr], y=df_plot['n_users'][gr], 
                   line_color=df_summary['col'][gr],
                   name=gr),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(x=[gr], y=[df_summary['n_users'][gr]],
               marker_color=df_summary['col'][gr],
               name=gr),
        row=1, col=2
    )
fig.update_layout(title_text='Total Users')
fig.update_xaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="N Users", row=1, col=1)
fig.update_xaxes(title_text="Groups", row=1, col=2)
fig.update_layout(yaxis_rangemode='tozero')
st.plotly_chart(fig)


fig = make_subplots(rows=1, cols=2, 
                    column_widths=[0.85, 0.15],
                    subplot_titles=("Daily", "Total"))
for gr in df_plot.index.unique():
    fig.add_trace(
        go.Scatter(x=df_plot['day'][gr], y=df_plot['conv'][gr], 
                   line_color=df_summary['col'][gr],
                   name=gr),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(x=[gr], y=[df_summary['conv'][gr]],
               marker_color=df_summary['col'][gr],
               name=gr),
        row=1, col=2
    )
fig.update_layout(title_text='Converted Users')
fig.update_xaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="N Converted", row=1, col=1)
fig.update_xaxes(title_text="Groups", row=1, col=2)
fig.update_layout(yaxis_rangemode='tozero')
st.plotly_chart(fig)


df_accum = df.groupby('group')[['n_users', 'conv']].cumsum().rename(columns={'n_users': 'n_users_accum', 'conv':'conv_accum'})
df = pd.concat([df, df_accum], axis=1)
df['p_accum'] = df['conv_accum'] / df['n_users_accum']

with st.spinner(text=f'Computing Conversions Interval Estimates ...'):
    hpdi = 0.95
    df[['p_hpdi_lower','p_hpdi_higher']] = df.apply(lambda row: pd.Series(hpdi_for_binom_and_uniform_prior(hpdi, row['conv_accum'], row['n_users_accum'])), axis=1)
    df['error_lower'] = df['p_accum'] - df['p_hpdi_lower']
    df['error_higher'] = df['p_hpdi_higher'] - df['p_accum']

df_plot = df.set_index('group')
df_summary[['p_error_lower', 'p_error_higher']] = df_plot[['error_lower', 'error_higher']][df_plot['day'] == df_plot['day'].max()]
df_summary[['p_hpdi_lower', 'p_hpdi_higher']] = df_plot[['p_hpdi_lower', 'p_hpdi_higher']][df_plot['day'] == df_plot['day'].max()]


fig = make_subplots(rows=1, cols=2,
                    shared_yaxes=True,
                    column_widths=[0.85, 0.15],
                    subplot_titles=("Daily", "Total"))
for gr in df_plot.index.unique():
    fig.add_trace(
        go.Scatter(x=df_plot['day'][gr], y=df_plot['p_accum'][gr],
                   line_color=df_summary['col'][gr],
                   name=gr),
        row=1, col=1)
    fig.add_trace(
        go.Scatter(x=pd.concat([df_plot['day'][gr], df_plot['day'][gr][::-1], df_plot['day'][gr][0:1]]),
                   y=pd.concat([df_plot['p_hpdi_higher'][gr], df_plot['p_hpdi_lower']
                                [gr][::-1], df_plot['p_hpdi_higher'][gr][0:1]]),
                   fill='toself', name=f'{hpdi:.0%} HPDI A',
                   hoveron='points+fills',
                   hoverinfo='text+x+y',
                   line_color=df_summary['col'][gr], fillcolor=df_summary['col'][gr], opacity=0.4),
        row=1, col=1)
    fig.add_trace(
        go.Scatter(x=[gr], y=[df_summary['p'][gr]],
                   marker_color=df_summary['col'][gr],
                   error_y={'array': [df_summary['p_error_higher'][gr]],
                            'arrayminus': [df_summary['p_error_lower'][gr]]},
                   name=gr),
        row=1, col=2)
fig.update_layout(title_text='Accumulated Conversions')
fig.update_xaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="Conversions", row=1, col=1)
fig.update_xaxes(title_text="Groups", row=1, col=2)
fig.update_layout(yaxis_rangemode='tozero', yaxis2_rangemode='tozero')
st.plotly_chart(fig)

summary_bar.progress(0.6)


widedf = df.set_index(['group', 'day']).unstack(level=0)
widedf['pb_gt_pa'] = widedf.apply(lambda row: prob_pb_gt_pa(
    p_a=row['p_accum']['A'],
    p_b=row['p_accum']['B'],
    N_a=row['n_users_accum']['A'], 
    N_b=row['n_users_accum']['B']), axis=1)
widedf = widedf.reset_index()
df_summary['p_best_group'] = pd.Series({'A': (1 - widedf['pb_gt_pa'].iloc[-1]), 'B':widedf['pb_gt_pa'].iloc[-1]})


fig = make_subplots(rows=1, cols=2, 
                    column_widths=[0.85, 0.15],
                    subplot_titles=("Daily Accumulated", "Total"))
fig.add_trace(go.Scatter(x=widedf.index, y=widedf['pb_gt_pa'],
                         name='P(p_B > p_A)', marker_color='orange',
                         opacity=0.6),
              col=1, row=1)
fig.add_hline(y=st.session_state['conv_pb_gt_pa_required'] / 100, line_dash="dash", col=1, row=1)
fig.add_hline(y=1 - st.session_state['conv_pb_gt_pa_required'] / 100, line_dash="dash", col=1, row=1)
for gr in df_summary.index.unique():
    fig.add_trace(
        go.Bar(x=[gr], y=[df_summary['p_best_group'][gr]],
               name=gr,
               marker_color=df_summary['col'][gr], width=0.3),
        row=1, col=2)
fig.update_layout(title_text='Certainty in Highest Conversion Group')
fig.update_xaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="P(p_B > p_A)", row=1, col=1)
fig.update_xaxes(title_text="Groups", row=1, col=2)
fig.update_layout(yaxis_rangemode='tozero', yaxis2_rangemode='tozero')
st.plotly_chart(fig)


n_sample = 100000
post_sample_a = posterior_sample_for_binom_and_uniform_prior(df_summary['conv']['A'], df_summary['n_users']['A'], n_sample)
post_sample_b = posterior_sample_for_binom_and_uniform_prior(df_summary['conv']['B'], df_summary['n_users']['B'], n_sample)
post_sample_rel = post_sample_b / post_sample_a
#pb_gt_pa = np.sum(post_sample_b > post_sample_a) / n_sample
#df_summary['p_best_group'] = pd.Series({'A': (1 - pb_gt_pa), 'B':pb_gt_pa})
#display(widedf.head())

fig = go.Figure()
p_grid = np.linspace(start=0, stop=1, num=3001)
xaxis_min = np.nan
xaxis_max = np.nan
for gr in df_summary.index.unique():
    post_dist = beta_post_dist(alpha=1, beta=1,
                               n_conv=df_summary['conv'][gr],
                               n_total=df_summary['n_users'][gr])
    xaxis_min = np.nanmin([xaxis_min, post_dist.mean() - 5 * post_dist.std()])
    xaxis_max = np.nanmax([xaxis_max, post_dist.mean() + 5 * post_dist.std()])
    y_plot = post_dist.pdf(p_grid)
    fig.add_trace(go.Scatter(x=p_grid, y=y_plot, mode='lines',
                             name=gr,
                             line_color=df_summary['col'][gr]))
xaxis_min = np.floor(xaxis_min * 100) / 100
xaxis_max = np.ceil(xaxis_max * 100) / 100
fig.update_xaxes(range=[xaxis_min, xaxis_max])
fig.update_layout(title='Conversions Prob Density Estimates',
                  yaxis_title='Prob Density',
                  xaxis_title='p',
                  hovermode="x")
st.plotly_chart(fig)


fig = go.Figure()
fig.add_trace(go.Histogram(x=post_sample_rel,
                           histnorm='probability density',
                           name='B/A', marker_color='orange',
                           opacity=0.6))
fig.add_vline(x=1, line_dash="dash")
fig.update_layout(title='Conversions Relation',
                  xaxis_title='p_B / p_A',
                  yaxis_title='Prob Density',
                  barmode='overlay')
st.plotly_chart(fig)


df_formatted['Mean Conversion, %'] = np.round(df_summary['p'] * 100, 1).astype(str)
#df_formatted['Conversion 95HPDI, %'] = df_summary.apply(lambda row: f"{row['p_hpdi_lower'] * 100 :.1f} - {row['p_hpdi_higher'] * 100:.1f}", axis=1)
#df_formatted['p (95 HPDI), %'] = df_summary.apply(lambda row: f"{row['p'] * 100 :.1f} ({row['p_hpdi_lower'] * 100 :.1f} - {row['p_hpdi_higher'] * 100:.1f})", axis=1)
df_formatted['Relative to A'] = pd.Series({'A':1.0, 'B':np.mean(post_sample_rel).round(2)}).astype(str)
summary_bar.progress(0.8)

df_formatted['Prob(Highest Conversion), %'] = np.round(df_summary['p_best_group'] * 100, 1).astype(str)
summary_bar.progress(1)
summary_bar.empty()
summary_container.table(df_formatted.T)


st.subheader("Duration Estimates")

col1, col2 = st.columns(2)
with col1: 
    st.number_input(label='Max Days in Simulations',
                    min_value=1,
                    step=1,
                    format='%d',
                    key='conv_sim_max_days')
with col2: 
    st.number_input(label='Simulations',
                    min_value=1,
                    step=1,
                    format='%d',
                    key='conv_n_simulations')

st.number_input(label='Required Certainty',
                min_value=0.0,
                step=1.0,
                format='%f',
                key='conv_pb_gt_pa_required')

n_simulations = st.session_state['conv_n_simulations']
pb_gt_pa_required = st.session_state['conv_pb_gt_pa_required'] / 100









a_alpha_post, a_beta_post = alpha_beta_post(alpha=1, beta=1,
                                            n_conv=df_summary['conv']['A'], 
                                            n_total=df_summary['n_users']['A'])
b_alpha_post, b_beta_post = alpha_beta_post(alpha=1, beta=1,
                                            n_conv=df_summary['conv']['B'], 
                                            n_total=df_summary['n_users']['B'])
a_post = stats.beta(a_alpha_post, a_beta_post)
b_post = stats.beta(b_alpha_post, b_beta_post)
a_p_sim = a_post.rvs(n_simulations)
b_p_sim = b_post.rvs(n_simulations)

trials = np.append(0, np.full(fill_value=st.session_state['conv_daily_users'],
                              shape=st.session_state['conv_sim_max_days']))
a_trials = np.rint(trials * (1 - conv_b_split)).astype(int)
b_trials = np.rint(trials * conv_b_split).astype(int)

i = 0
with st.spinner(text=f'Running {n_simulations} simulations ...'):
    my_bar = st.progress(0)
    sims = []
    for a_p, b_p in zip(a_p_sim, b_p_sim):
        s = {}
        s['A'] = simulate(a_p, a_trials, a_alpha_post, a_beta_post)
        s['B'] = simulate(b_p, b_trials, b_alpha_post, b_beta_post)
        s['pb_ge_pa'] = pb_ge_pa_sims(s['A'], s['B'], n_cmp=10000)
        s['days'] = np.arange(st.session_state['conv_sim_max_days'] + 1)
        s['N'] = s['A']['trials_accum'] + s['B']['trials_accum']
        s['pb_gt_pa_required'] = st.session_state['conv_pb_gt_pa_required'] / 100
        s['min_days_to_reach_certainty_lvl'] = min_days_to_reach_certainty_level(s['pb_ge_pa'], s['days'], s['pb_gt_pa_required'])
        sims.append(s)
        i = i + 1
        my_bar.progress(i / n_simulations)
my_bar.empty()

n_reached_hist = [s['min_days_to_reach_certainty_lvl'] for s in sims]
n_reached_freqs = pd.Series(n_reached_hist).value_counts(normalize=True).rename('freq').to_frame()
x_med = np.median(n_reached_hist)
if len(n_reached_freqs['freq']) == 1:
    summary_line = f"100% simulations reached certainty at day {n_reached_freqs.index[0]}"
else:
    summary_line = f"50% simulations reached {pb_gt_pa_required*100:.0f}% certainty at additional day {x_med:.0f} or earlier"

summary_container.write(f"""
    Current P(p_B > p_A): {df_summary['p_best_group']['B'] * 100:.1f}%    
    Required certainty: {st.session_state['conv_pb_gt_pa_required']}%  
    {summary_line}
""")

fig = go.Figure()
fig.add_trace(go.Bar(x=n_reached_freqs.index,
                     y=n_reached_freqs['freq'],
                     width=[1] * len(n_reached_freqs),
                     marker_color='red',
                     opacity=0.6,
                     name='Simulations Reached Certainty'))
fig.add_trace(go.Scatter(x=[x_med, x_med], y=[0, np.max(n_reached_freqs['freq'])], 
                         line_color='black',
                         line_dash='dash',
                         mode='lines',
                         hovertemplate=f"Median: {x_med}",
                         name='Median'))              
fig.update_layout(title=f'Additional Days to Reach {pb_gt_pa_required*100:.0f}% Certainty')
fig.update_layout(xaxis_title='Additional Days',
                  yaxis_title='Part from Total Simulations',
                  showlegend=False)
fig.update_xaxes(range=[0, st.session_state['conv_sim_max_days'] + 1])
fig.update_layout(yaxis_rangemode='tozero')
st.plotly_chart(fig)

st.markdown('---')
st.write("Sources: https://github.com/noooway/Coinflip")
st.write("Theory: https://github.com/noooway/Bayesian_ab_testing")
