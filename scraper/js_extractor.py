"""JS snippets + parsers for Upwork search and job-detail pages."""

import json


JS_GET_JOB_LINKS = r"""
(function(){
    var seen={}, links=[], re=/upwork\.com\/(jobs|freelance-jobs)\/.+~[\w]+/;
    document.querySelectorAll('a[href]').forEach(function(a){
        var h=a.href||'';
        if(re.test(h)){var k=h.split('?')[0]; if(!seen[k]){seen[k]=1;links.push(h);}}
    });
    return JSON.stringify(links);
})()
"""

JS_GET_NEXT_PAGE = r"""
(function(){
    var el=document.querySelector('a[data-test="pagination-next"],[aria-label="Next page"]');
    return el?el.href:null;
})()
"""

JS_GET_JOB_INFO = r"""
(function(){
    function t(ss){
        for(var i=0;i<ss.length;i++){
            var e=document.querySelector(ss[i]);
            if(e){var v=(e.innerText||e.textContent||'').trim();if(v)return v;}
        }
        return '';
    }
    function all(ss){
        for(var i=0;i<ss.length;i++){
            var es=document.querySelectorAll(ss[i]);
            if(es.length)return Array.from(es).map(function(e){
                return(e.innerText||e.textContent||'').trim();
            }).filter(Boolean);
        }
        return[];
    }

    // client location has a time suffix - strip it
    var locRaw = t(['[data-qa="client-location"]','li[data-test="client-location"] strong']);
    var loc = locRaw ? locRaw.split('\n')[0].trim() : '';

    // parse duration/category/hours from page title as fallback
    var pgTitle = document.title || '';
    var tDuration='', tCategory='', tHours='';
    pgTitle.split(' - ').forEach(function(p){
        p=p.trim();
        if(/month|week|year/i.test(p)&&!/hrs/i.test(p)) tDuration=p;
        else if(/hrs\/week|hour/i.test(p)) tHours=p;
        else if(/^Freelance Job in /i.test(p)) tCategory=p.replace(/^Freelance Job in /i,'').trim();
    });

    return JSON.stringify({
        title:            t(['h1[data-test="job-title"]','h1.m-0-bottom','h1']),
        description:      t(['[data-test="Description"]','[data-test="description"] .break','div.break','[data-test="description"]']),
        budget:           t(['[data-test="budget"]','[data-qa="budget"]','li[data-test="budget"] strong']),
        job_type:         t(['li[data-test="job-type-label"]','[data-qa="job-type"]','[data-test="engagement"]']),
        experience_level: t(['li[data-test="experience-level"]','[data-qa="experience-level"]']),
        duration:         t(['li[data-test="duration-label"]','[data-qa="duration"]'])||tDuration,
        hours_per_week:   t(['[data-test="hours-per-week"]','[data-qa="hours-per-week"]'])||tHours,
        posted_at:        t(['span[data-test="posted-on"]','[data-qa="posted-on"]','time']),
        category:         t(['a[data-test="attr-item"][href*="category"]','li[data-test="category"] a','[data-qa="category"]'])||tCategory,
        skills:           all(['a[data-test="skill"]','[data-qa="skill"]','span.air3-badge-tagline']),
        proposals:        t(['li[data-test="proposals-tier"]','[data-qa="proposals"]']),
        client_country:   loc,
        client_rating:    t(['[data-test="client-rating"] .air3-rating-value-text','[data-qa="client-rating"]']),
        client_total_spent: t(['[data-qa="client-spend"]','li[data-test="client-spendings"] strong']),
        client_hires:     t(['[data-qa="client-hires"]','li[data-test="client-hires"] strong']),
        client_member_since: t(['[data-qa="client-contract-date"]'])
    });
})()
"""

JS_GET_NEXT_JOB = r"""
(function(){
    var el=document.querySelector('a[data-test="next-job"],a[aria-label="Next job"]');
    return el?el.href:null;
})()
"""

JS_IS_CHALLENGE = r"""
(function(){
    var t=document.title.toLowerCase();
    return t.indexOf('challenge')!==-1||t.indexOf('just a moment')!==-1;
})()
"""

JS_HAS_JOBS = r"""
document.querySelectorAll('a[href*="~"]').length > 0
"""

JS_HAS_H1 = r"""
document.querySelector('h1') !== null
"""

JS_DEBUG_DUMP = r"""
(function(){
    var out={};
    document.querySelectorAll('[data-test]').forEach(function(el){
        var k=el.getAttribute('data-test');
        var v=(el.innerText||el.textContent||'').trim().slice(0,200);
        if(v) out['[data-test="'+k+'"]']=v;
    });
    document.querySelectorAll('[data-qa]').forEach(function(el){
        var k=el.getAttribute('data-qa');
        var v=(el.innerText||el.textContent||'').trim().slice(0,200);
        if(v) out['[data-qa="'+k+'"]']=v;
    });
    document.querySelectorAll('h1,h2,h3').forEach(function(el,i){
        out['heading_'+i+'_'+el.tagName]=(el.innerText||'').trim().slice(0,200);
    });
    out['__title__']=document.title;
    out['__url__']=window.location.href;
    return JSON.stringify(out,null,2);
})()
"""


def parse_job_info(raw_json: str | None, url: str) -> dict:
    """Always returns a dict — empty fields kept, nothing skipped."""
    info: dict = {"url": url}
    if raw_json:
        try:
            info.update(json.loads(raw_json))
        except Exception:
            pass
    info["url"] = url
    if isinstance(info.get("skills"), list):
        info["skills"] = json.dumps(info["skills"])
    return info
