"""PROJECT HOPE v3.0 - Probability Calculator (Black-Scholes public math)"""
import math

def norm_cdf(x):
    a1=0.254829592;a2=-0.284496736;a3=1.421413741;a4=-1.453152027;a5=1.061405429;p=0.3275911
    sign=1 if x>=0 else -1;x=abs(x)/math.sqrt(2)
    t=1.0/(1.0+p*x);y=1.0-(((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.exp(-x*x)
    return 0.5*(1.0+sign*y)

def prob_otm(S,K,T,sigma,option_type='put'):
    if T<=0 or sigma<=0: return 0
    d2=(math.log(S/K)+(-sigma**2/2)*T)/(sigma*math.sqrt(T))
    return round(norm_cdf(d2)*100,1) if option_type=='put' else round(norm_cdf(-d2)*100,1)

def prob_profit_spread(S,short_strike,credit,T,sigma,spread_type='put_credit'):
    if T<=0 or sigma<=0: return 0
    be=short_strike-credit if spread_type=='put_credit' else short_strike+credit
    d2=(math.log(S/be)+(-sigma**2/2)*T)/(sigma*math.sqrt(T))
    return round(norm_cdf(d2)*100,1) if spread_type=='put_credit' else round(norm_cdf(-d2)*100,1)

def expected_value(prob_profit,max_profit,max_loss):
    pp=prob_profit/100
    return round((pp*max_profit)-((1-pp)*abs(max_loss)),2)

def calculate_spread_metrics(stock_price,short_strike,long_strike,credit,dte,iv):
    T=dte/365;sigma=iv/100 if iv>1 else iv
    spread_type='put_credit' if short_strike<stock_price else 'call_credit'
    max_profit=credit*100;sw=abs(short_strike-long_strike);max_loss=(sw-credit)*100
    be=short_strike-credit if spread_type=='put_credit' else short_strike+credit
    p_otm=prob_otm(stock_price,short_strike,T,sigma,'put' if spread_type=='put_credit' else 'call')
    p_profit=prob_profit_spread(stock_price,short_strike,credit,T,sigma,spread_type)
    ev=expected_value(p_profit,max_profit,max_loss)
    ror=round((credit/(sw-credit))*100,1) if (sw-credit)>0 else 0
    return {'spread_type':spread_type,'stock_price':stock_price,'short_strike':short_strike,
            'long_strike':long_strike,'credit':credit,'max_profit':max_profit,'max_loss':max_loss,
            'spread_width':sw,'breakeven':round(be,2),'prob_otm':p_otm,'prob_profit':p_profit,
            'expected_value':ev,'return_on_risk':ror,'dte':dte,'iv':round(iv,1)}
