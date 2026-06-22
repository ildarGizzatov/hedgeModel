const API="http://localhost:8083";

// === Tabs ===
document.querySelectorAll(".tab").forEach(function(t){
  t.addEventListener("click",function(){
    document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});
    document.querySelectorAll(".tab-content").forEach(function(x){x.classList.remove("active")});
    t.classList.add("active");
    document.getElementById("tab-"+t.dataset.tab).classList.add("active");
  });
});

// === Helpers ===
function F(v,d){
  d=d||2;
  return Number(v).toLocaleString("ru-RU",{minimumFractionDigits:d,maximumFractionDigits:d});
}
function P(v){return(v>=0?"+":"")+F(v)+"%";}
function U(v){return(v>=0?"+$":"-$")+F(Math.abs(v));}
function clr(v){return v>=0?"green":"red";}
function B(a){
  var c=a==="CLOSE"?"badge-close":a==="ROLL"?"badge-roll":"badge-hold";
  return '<span class="badge '+c+'">'+(a==="CLOSE"?"ЗАКРЫТЬ":a==="ROLL"?"РОЛЛ":"ДЕРЖАТЬ")+'</span>';
}
function PB(p){
  var c=p==="high"?"badge-high":p==="medium"?"badge-medium":"badge-low";
  return '<span class="badge '+c+'">'+(p==="high"?"Высокий":p==="medium"?"Средний":"Низкий")+'</span>';
}

// === Bar chart (vanilla canvas, no deps) ===
function drawBar(canvasId, labels, data, colors){
  var canvas=document.getElementById(canvasId);
  if(!canvas) return;
  var ctx=canvas.getContext("2d");
  var box=canvas.parentElement;
  var W=box.clientWidth-32, H=228;
  canvas.width=W; canvas.height=H;
  ctx.clearRect(0,0,W,H);
  var pt=20,pr=20,pb=50,pl=70;
  var cW=W-pl-pr, cH=H-pt-pb;
  // Range
  var mn=0, mx=0;
  for(var i=0;i<data.length;i++){
    if(data[i]<mn) mn=data[i];
    if(data[i]>mx) mx=data[i];
  }
  var rng=mx-mn;
  if(rng===0){mn=-1;mx=1;rng=2;}
  // Grid lines
  ctx.strokeStyle="#30363d";ctx.lineWidth=1;
  ctx.fillStyle="#8b949e";ctx.font="11px monospace";ctx.textAlign="right";
  for(var i=0;i<=4;i++){
    var val=mn+rng*i/4;
    var y=pt+cH-cH*i/4;
    ctx.fillText(F(val),pl-8,y+4);
    ctx.beginPath();ctx.moveTo(pl,y);ctx.lineTo(W-pr,y);ctx.stroke();
  }
  // Zero line
  if(mn<0&&mx>0){
    var zeroY=pt+cH*(1-(0-mn)/rng);
    ctx.strokeStyle="#58a6ff44";ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(pl,zeroY);ctx.lineTo(W-pr,zeroY);ctx.stroke();
    ctx.setLineDash([]);
  }
  // Bars
  var gW=cW/labels.length, barW=Math.min(30,gW);
  for(var i=0;i<data.length;i++){
    var barH=Math.abs(data[i]/rng*cH);
    var baseY=(zeroY>=pt)?zeroY:pt;
    var x=pl+i*gW+gW/2-barW/2;
    var y=data[i]>=0?baseY-barH:baseY;
    ctx.fillStyle=colors?colors[i]:(data[i]>=0?"#3fb950":"#f85149");
    ctx.fillRect(x,y,barW-2,barH);
  }
  // Labels
  ctx.fillStyle="#8b949e";ctx.font="11px monospace";ctx.textAlign="center";
  for(var i=0;i<labels.length;i++){
    ctx.fillText(labels[i],pl+i*gW+gW/2,H-pb+20);
  }
}

function refreshUI(){
  document.getElementById('headerUpdated').textContent='Загрузка...';
}

function setBtnAction(id, text, loading){
  var btn=document.querySelector('#refresh'+id+' .btn-action');
  if(!btn)return;
  if(loading){
    btn.classList.add("spinning");
    btn.disabled=true;
  } else {
    btn.classList.remove("spinning");
    btn.disabled=false;
  }
  if(!loading) btn.textContent=text;
}

function refreshAll(){
  loadAll();
}

function refreshPrices(){
  var id="1";
  setBtnAction(id, "🔄 Цены", true);
  fetch(API+"/api/refresh-prices", {method:"POST"}).then(function(r){return r.json();}).then(function(res){
    if(res.status==="ok"){
      loadAll();
      setBtnAction(id, "✅ Цены обновлены", false);
    } else {
      setBtnAction(id, "❌ Ошибка", false);
      alert("Ошибка обновления цен: "+res.output);
    }
    setTimeout(function(){setBtnAction(id, "🔄 Цены", false);},3000);
  }).catch(function(e){
    setBtnAction(id, "❌ Ошибка", false);
    alert("Ошибка: "+e.message);
    setTimeout(function(){setBtnAction(id, "🔄 Цены", false);},3000);
  });
}

function updateOptions(){
  var id="2";
  setBtnAction(id, "⚡ Обновить опционы", true);
  fetch(API+"/api/update-options", {method:"POST"}).then(function(r){return r.json();}).then(function(res){
    if(res.status==="ok"){
      loadAll();
      setBtnAction(id, "✅ Обновлено", false);
    } else {
      setBtnAction(id, "❌ Ошибка", false);
      alert("Ошибка обновления: "+res.output);
    }
    setTimeout(function(){setBtnAction(id, "⚡ Обновить опционы", false);},3000);
  }).catch(function(e){
    setBtnAction(id, "❌ Ошибка", false);
    alert("Ошибка: "+e.message);
    setTimeout(function(){setBtnAction(id, "⚡ Обновить опционы", false);},3000);
  });
}

function runAnchor(){
  var id="3";
  setBtnAction(id, "🎯 Anchor Layer", true);
  // Перезагружаем рекомендации и позиции
  Promise.all([
    api("/api/positions"),
    api("/api/recommendations"),
    api("/api/summary"),
  ]).then(function(results){
    renderPositions(results[0]);
    renderRecommendations(results[1]);
    renderSummary(results[2], results[0]);
    setBtnAction(id, "✅ Обновлено", false);
  }).catch(function(e){
    setBtnAction(id, "❌ Ошибка", false);
    alert("Ошибка: "+e.message);
  });
}

// === Fetch helpers ===
function api(path){
  return fetch(API+path).then(function(r){return r.json();}).catch(function(e){return null;});
}

// === TAB 1: POSITIONS ===
function renderPositions(pos){
  var posT=document.getElementById("posTable");
  var posS=document.getElementById("posSummary");
  var upd=document.getElementById("headerUpdated");
  if(!pos){
    posT.innerHTML='<tr><td colspan="7" style="color:var(--red)">Ошибка загрузки</td></tr>';
    return;
  }
  var t=pos.totals;
  var pc=clr(t.total_pnl);
  posS.innerHTML=
    '<div class="summary-card"><div class="label">Total Cost</div><div class="value">$'+F(t.total_cost)+'</div></div>'+
    '<div class="summary-card"><div class="label">Current Value</div><div class="value">$'+F(t.total_value)+'</div></div>'+
    '<div class="summary-card"><div class="label">PnL</div><div class="value '+pc+'">'+U(t.total_pnl)+'</div><div class="sub '+pc+'">'+P(t.total_pnl_pct)+'</div></div>';
  upd.textContent="Обновлено: "+pos.updated;
  var rows="";
  pos.positions.forEach(function(p){
    var pc2=clr(p.pnl);
    var z=p.avg_price>p.current_price?'<span style="color:var(--red)">Просадка</span>':'<span style="color:var(--green)">Прибыль</span>';
    rows+='<tr><td><b>'+p.symbol+'</b></td><td>'+F(p.qty,2)+'</td><td>$'+F(p.avg_price)+'</td><td>$'+F(p.current_price)+'</td><td class="'+pc2+'">'+U(p.pnl)+'</td><td class="'+pc2+'">'+P(p.pnl_pct)+'</td><td>'+z+'</td></tr>';
  });
  posT.innerHTML=rows;

  // === Buy history ===
  var buyEl=document.getElementById("buyHistoryTable");
  if(buyEl){
    var totalBuyPnl=0;
    var html="";
    var buys=pos.buy_history||[];
    buys.forEach(function(b){
      totalBuyPnl+=b.pnl;
      var pc3=clr(b.pnl);
      html+='<tr class="buy-row"><td>'+b.date+'</td><td>'+b.qty+'</td><td>$'+F(b.price)+'</td><td>$'+F(b.total)+'</td><td class="'+pc3+'">'+U(b.pnl)+'</td><td class="'+pc3+'">'+P(b.pnl_pct)+'</td><td style="color:var(--text-dim)">'+(b.notes||'')+'</td></tr>';
    });
    buyEl.innerHTML=html||'<tr><td colspan="7" style="color:var(--text-dim)">Нет данных</td></tr>';
    document.getElementById("buyCount").textContent=buys.length;
    var pnlEl=document.getElementById("buyTotalPnl");
    if(pnlEl){pnlEl.className=clr(totalBuyPnl);pnlEl.textContent=U(totalBuyPnl)}
  }

  // === Drop 20% from current price (step $1) ===
  var dropEl=document.getElementById("posDrop");
  if(dropEl && pos.positions.length>0){
    var p=pos.positions[0];
    var current=p.current_price;
    var low20=Math.round(current*0.80);
    var rows="";
    for(var price=low20;price<=current;price++){
      var dPnl=(price-p.avg_price)*p.qty;
      var dPnlPct=((price-p.avg_price)/p.avg_price*100);
      var dropPct=((price-current)/current*100);
      var cls=clr(dPnl);
      var icon="";
      if(price===Math.round(current)) icon=" 🔵";
      else if(price===Math.round(p.avg_price)) icon=" 📍";
      else if(dPnl>=0) icon=" 🟢";
      else icon=" 🔴";
      rows+='<tr><td class="'+cls+'">$'+price+icon+'</td>';
      rows+='<td class="'+cls+'">'+U(dPnl)+'</td>';
      rows+='<td class="'+cls+'">'+P(dPnlPct)+'</td>';
      rows+='<td class="'+cls+'">'+P(dropPct)+'</td></tr>';
    }
    dropEl.innerHTML=rows;
  }
}

// === TAB 2: OPTIONS ===
function renderOptions(opt, pos){
  var optT=document.getElementById("optTable");
  if(!opt){
    optT.innerHTML='<tr><td colspan="12" style="color:var(--red);text-align:center">Ошибка загрузки</td></tr>';
    return;
  }
  var t=opt.totals;
  var rows="";
  opt.options.forEach(function(o){
    var pc2=clr(o.pnl);
    var ivClr=o.iv_change>=0?"green":"red";
    rows+='<tr style="text-align:left">';
    rows+='<td>'+o.symbol+'</td>';
    rows+='<td class="layer-'+o.layer+'">'+o.layer+'</td>';
    rows+='<td>'+o.qty+'</td>';
    rows+='<td>$'+o.strike+'</td>';
    rows+='<td>$'+F(o.entry_price,2)+'</td>';
    rows+='<td>$'+F(o.current_price,2)+'</td>';
    rows+='<td class="'+pc2+'">'+U(o.pnl)+'</td>';
    rows+='<td title="Entry: '+F(o.delta_entry,4)+'\nИзменение: '+F(o.delta_change,4)+'">'+F(o.delta,4)+'</td>';
    rows+='<td title="Entry: '+F(o.gamma_entry,4)+'\nИзменение: '+F(o.gamma_change,4)+'">'+F(o.gamma,4)+'</td>';
    rows+='<td class="'+pc2+'" title="Entry: '+F(o.theta_entry,4)+'\nНа день: '+F(o.theta_per_day,4)+'">'+F(o.theta_per_day,4)+'</td>';
    rows+='<td title="Entry: '+F(o.iv_entry,4)+'\nИзменение: '+F(o.iv_change,4)+'">'+F(o.iv,4)+'</td>';
    rows+='<td class="'+ivClr+'" title="Входной IV: '+F(o.iv_entry,4)+'\nТекущий IV: '+F(o.iv,4)+'\nИзменение: '+F(o.iv_change,4)+'">'+F(o.iv_change,4)+'</td>';
    rows+='</tr>';
  });
  optT.innerHTML=rows;
  // Net Greeks — итоговая строка внизу таблицы
  var tEl=document.getElementById("optTable");
  if(tEl){
    tEl.insertAdjacentHTML("beforeend",
      '<tr style="background:var(--surface);border-top:2px solid var(--border);font-weight:700"><td colspan="3" style="color:var(--blue);font-size:15px">Итого</td><td></td><td></td><td></td><td style="'+clr(t.total_pnl)+';font-size:15px">'+U(t.total_pnl)+'</td><td style="font-size:15px">'+F(t.net_delta,4)+'</td><td style="font-size:15px">'+F(t.net_gamma,4)+'</td><td style="font-size:15px">'+F(t.net_theta,4)+'</td><td style="font-size:15px">'+F(t.net_vega,4)+'</td><td></td></tr>');
  }

  // === Duplicate options table for Recommendations tab (with DTE) ===
  var optRecEl=document.getElementById("optTableRec");
  if(optRecEl && opt.options.length>0){
    var rowsRec="";
    opt.options.forEach(function(o){
      var pc2=clr(o.pnl);
      rowsRec+='<tr style="text-align:left">';
      rowsRec+='<td>'+o.symbol+'</td>';
      rowsRec+='<td>'+F(o.entry_price*o.qty,2)+'</td>';
      rowsRec+='<td class="'+pc2+'">'+U(o.pnl)+'</td>';
      rowsRec+='<td class="layer-'+o.layer+'">'+o.layer+'</td>';
      rowsRec+='<td>'+o.dte+'</td>';
      rowsRec+='<td title="Entry: '+F(o.delta_entry,4)+'\nИзменение: '+F(o.delta_change,4)+'">'+F(o.delta,4)+'</td>';
      rowsRec+='<td title="Entry: '+F(o.gamma_entry,4)+'\nИзменение: '+F(o.gamma_change,4)+'">'+F(o.gamma,4)+'</td>';
      rowsRec+='<td class="'+pc2+'" title="Entry: '+F(o.theta_entry,4)+'\nНа день: '+F(o.theta_per_day,4)+'">'+F(o.theta_per_day,4)+'</td>';
      rowsRec+='<td title="Entry: '+F(o.iv_entry,4)+'\nИзменение: '+F(o.iv_change,4)+'">'+F(o.iv,4)+'</td>';
      rowsRec+='</tr>';
    });
    optRecEl.innerHTML=rowsRec;
  }

  // === PnL Ladder (step $1, ±20%) ===
  var ladderEl=document.getElementById("posLadder");
  if(ladderEl && pos && pos.positions && pos.positions.length>0){
    var solLadder=pos.pnl_ladder||[];
    var combIdx={};
    ((combinedLadder||{}).ladder||[]).forEach(function(r){combIdx[r.price]=r;});
    var html="";
    solLadder.forEach(function(row){
      var cls=row.is_current?"color:var(--blue);font-weight:700":clr(row.pnl);
      var icon="";
      if(row.is_current) icon=" 🔵";
      else if(row.is_avg) icon=" 📍";
      else if(row.pnl>=0) icon=" 🟢";
      else icon=" 🔴";
      var c=combIdx[row.price];
      var combPnl=c?c.total_pnl:0;
      var optPnl=combPnl-row.pnl;
      html+='<tr><td class="'+cls+'">$'+row.price+icon+'</td><td class="'+cls+'">'+P(row.pnl_pct)+'</td><td class="'+cls+'">'+U(row.pnl)+'</td><td class="'+cls+'">'+U(combPnl)+'</td><td class="'+clr(optPnl)+'">'+U(optPnl)+'</td></tr>';;
    });
    ladderEl.innerHTML=html;
  }
}

// === TAB 3: RECOMMENDATIONS ===
function renderLayers(l){
  if(!l){return;}
  var cards=document.getElementById("layerCards");
  if(!cards)return;
  var html="";
  html+='<div style="display:flex;gap:8px">';
  l.layers.forEach(function(ly){
    var usedPct=0;
    if(ly.budget && ly.budget>0) usedPct=parseFloat(ly.spent)/parseFloat(ly.budget)*100;
    var barColor=usedPct>=90?'var(--red)':usedPct>=50?'var(--yellow)':'var(--green)';
    var pnlCls=ly.pnl!==0?(ly.pnl>0?'green':'red'):'';
    html+='<div style="flex:1;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px;display:flex;flex-direction:column">';
    html+='<div style="font-size:18px;font-weight:600">'+ly.name+'</div>';
    html+='<div style="font-size:14px;color:var(--text-dim);margin-top:2px">$'+F(ly.budget,2)+' бюджет</div>';
    html+='<div style="font-size:14px;color:var(--text-dim)">$'+F(ly.spent,2)+' потрачено ('+Math.round(usedPct)+'%)</div>';
    // Horizontal bar
    html+='<div style="margin:8px 0">';
    html+='<div style="height:10px;background:#30363d;border-radius:5px;overflow:hidden"><div style="width:'+Math.min(usedPct,100)+'%;height:100%;background:'+barColor+';border-radius:5px"></div></div>';
    html+='<div style="font-size:13px;color:var(--text-dim);text-align:right;margin-top:3px">'+Math.round(usedPct)+'%</div>';
    html+='</div>';
    // Result
    html+='<div style="display:flex;justify-content:space-between;padding-top:6px;border-top:1px solid var(--border)">';
    html+='<div><div style="font-size:14px;color:var(--text-dim)">PnL</div>';
    html+='<div class="'+pnlCls+'" style="font-size:16px;font-weight:600">'+(ly.pnl!==0?((ly.pnl>=0?"+$":"-$")+F(Math.abs(ly.pnl))):'—')+'</div></div>';
    html+='<div><div style="font-size:14px;color:var(--text-dim)">Опционов</div>';
    html+='<div style="font-size:16px;font-weight:600">'+ly.count+'</div></div>';
    html+='</div>';
    html+='</div>';
  });
  html+='</div>';
  cards.innerHTML=html;
}

function renderRecommendations(rec){
  var ai=document.getElementById("anchorInfo");
  var rl=document.getElementById("recList");
  if(!rec){
    ai.innerHTML='<div style="color:var(--red)">Ошибка загрузки</div>';
    rl.innerHTML='<div style="color:var(--red)">Ошибка загрузки</div>';
    return;
  }
  // Anchor info
  if(rec.anchor&&rec.anchor.length){
    var a=rec.anchor[0];
    ai.innerHTML='<div class="rec-item"><div><b>Avg Buy:</b> $'+F(a.avg_price)+' | <b>Target:</b> $'+F(a.s_target)+'<br><b>Position Size:</b> $'+F(a.position_size)+' | <b>Anchor Budget:</b> $'+F(a.anchor_budget)+' | <b>SOL qty:</b> '+F(a.qty,2)+'</div></div>';
  }
  // Suggestions
  var recs=rec.suggestions||[];
  if(recs.length===0){
    rl.innerHTML='<div style="color:var(--text-dim);padding:12px">Нет рекомендаций — все позиции в норме</div>';
  } else {
    var html="";
    recs.forEach(function(s){
      var ac=s.recommendation.action;
      var cls="action-"+ac.toLowerCase();
      html+='<div class="rec-item '+cls+'">'+
        '<div class="rec-meta"><b>'+s.symbol+'</b><br>'+
        'Strike $'+s.strike+' | DTE '+s.dte+' | PnL '+F(s.pnl_pct)+'%<br><br>'+
        B(ac)+' '+PB(s.recommendation.priority)+'</div>'+
        '<div class="rec-detail">'+ac+' — '+s.recommendation.reason+'</div></div>';
    });
    rl.innerHTML=html;
  }
}

// === TAB 4: SUMMARY ===
function renderSummary(sum, opt){
  var ts=document.getElementById("totalSummary");
  if(!sum){
    ts.innerHTML='<div style="color:var(--red)">Ошибка загрузки</div>';
    return;
  }
  var t=sum.total;
  var assetsPnl=clr(sum.assets.total_pnl);
  var optPnl=clr(sum.options.total_pnl);
  var totalPnl=clr(t.total_pnl);
  ts.innerHTML=
    '<div class="summary-card"><div class="label">Assets PnL</div><div class="value '+assetsPnl+'">'+U(sum.assets.total_pnl)+'</div><div class="sub '+assetsPnl+'">'+P(sum.assets.total_pnl_pct)+'</div></div>'+
    '<div class="summary-card"><div class="label">Options PnL</div><div class="value '+optPnl+'">'+U(sum.options.total_pnl)+'</div><div class="sub '+optPnl+'">'+P(sum.options.total_pnl_pct)+'</div></div>'+
    '<div class="summary-card"><div class="label">Общий PnL</div><div class="value '+totalPnl+'">'+U(t.total_pnl)+'</div><div class="sub '+totalPnl+'">'+P(t.total_pnl_pct)+'</div></div>';
}

// === LAYER TABS ===
var layerFilterParams={distant:"",mid:"",near:""};
var selectedOption={distant:null,mid:null,near:null};
var layerDefaults={distant:{delta_min:0.05,delta_max:0.20,dte_min:25,dte_max:99999},mid:{delta_min:0.20,delta_max:0.40,dte_min:10,dte_max:25},near:{delta_min:0.38,delta_max:0.55,dte_min:5,dte_max:10}};
var purchasedOptions={distant:[],mid:[],near:[]};

window.__so = function(layer,symbol){
  selectOption(layer,symbol);
};

window.__as = function(layer,symbol){
  // Double-click: populate selectedOption even if click didn't fire
  var data;
  if(layer==='distant') data=layerData_distant;
  else if(layer==='mid') data=layerData_mid;
  else data=layerData_near;
  var found=null;
  if(data && data.options){
    for(var i=0;i<data.options.length;i++){
      if(data.options[i].symbol===symbol){found=data.options[i];break;}
    }
  }
  if(found){
    selectedOption[layer]={symbol:symbol, strike:found.strike, dte:found.dte, iv:found.iv, price:found.price, delta:found.delta, gamma:found.gamma, theta:found.theta, vega:found.vega};
  } else {
    selectedOption[layer]={symbol:symbol};
  }
  console.log('__as: selectedOption='+JSON.stringify(selectedOption[layer]));
  addSelected(layer,symbol);
};

function renderLayer(data){
  if(!data) return;
  var layer=data.layer;
  var el=document.getElementById("layerContent-"+layer);
  var t=document.getElementById("layerTitle-"+layer);
  if(!el) return;
  if(t) t.textContent=data.label;
  var purchasedCount=0;
  var html='<div style="margin-bottom:8px;font-size:13px;color:var(--text-dim)">Delta '+data.criteria.delta_min+'–'+data.criteria.delta_max+' | DTE '+(data.criteria.dte_max==="all"?"all":data.criteria.dte_min+'–'+data.criteria.dte_max)+' | '+(data.spot_price?'Spot: $'+F(data.spot_price,2)+' ':'')+'Всего: <b>'+data.count+'</b></div>';
  var opts=data.options||[];
  if(opts.length===0){html+='<div style="padding:12px;color:var(--text-dim)">Нет опционов</div>';el.innerHTML=html;return;}
  html+='<div style="max-height:220px;overflow-y:auto;border:1px solid var(--border);border-radius:4px"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:3px 6px">Символ</th><th style="padding:3px 6px;text-align:right">Strike</th><th style="padding:3px 6px;text-align:center">DTE</th><th style="padding:3px 6px;text-align:right">Δ</th><th style="padding:3px 6px;text-align:right">IV</th><th style="padding:3px 6px;text-align:right">Θ</th><th style="padding:3px 6px;text-align:right">ν</th><th style="padding:3px 6px;text-align:right">Price</th><th style="padding:3px 6px;text-align:center">Метка</th></tr></thead><tbody>';
  opts.forEach(function(o){
    var rowCls=o.is_layer_match?'background:rgba(63,185,80,0.12);':'';
    var sym=o.symbol.replace(/'/g,"\\'");
    var title='Один клик: выделить, двойной: добавить | IV ATM: '+F(o.iv_atm,4);
    html+='<tr style="text-align:left;height:24px;cursor:pointer;'+rowCls+' onclick="window.__so(\''+layer+'\',\''+sym+'\')" ondblclick="event.preventDefault();event.stopPropagation();window.__as(\''+layer+'\',\''+sym+'\')" title="'+title+'">';
    html+='<td style="padding:2px 6px;font-weight:bold">'+o.symbol+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+o.strike+'</td>';
    html+='<td style="padding:2px 6px;text-align:center">'+o.dte+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.delta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.iv,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.theta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.vega,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(o.price,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:center">'+(o.is_layer_match?'<span style="color:var(--green);font-weight:bold">✓</span>':'<span style="color:var(--text-dim)">·</span>')+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  el.innerHTML=html;
}

function selectOption(layer,symbol,o){
  try {
    if(o){
      selectedOption[layer]={symbol:symbol, strike:o.strike, dte:o.dte, iv:o.iv, price:o.price, delta:o.delta, gamma:o.gamma, theta:o.theta, vega:o.vega};
    } else if(layerData_distant&&layerData_distant.options&&layer==='distant'){
      var f=layerData_distant.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer]=f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega}:{symbol:symbol};
    } else if(layerData_mid&&layerData_mid.options&&layer==='mid'){
      var f=layerData_mid.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer]=f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega}:{symbol:symbol};
    } else if(layerData_near&&layerData_near.options&&layer==='near'){
      var f=layerData_near.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer]=f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega}:{symbol:symbol};
    } else {
      selectedOption[layer]={symbol:symbol};
    }
    console.log('selectOption:', layer, selectedOption[layer]);
  } catch(e){ console.error('selectOption error:',e); }
  var params=layerFilterParams[layer]?"?"+layerFilterParams[layer]:"";
  api("/api/layer-"+layer+params).then(function(d){renderLayer(d);});
}

function addSelected(layer,symbol){
  try {
    var sel=selectedOption[layer];
    if(!sel||!sel.symbol){alert('Сначала кликните на опцион');return;}
    var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
    if(!selList[layer]) selList[layer]=[];
    if(!selList[layer].find(function(x){return x.symbol===sel.symbol})){
      var item=JSON.parse(JSON.stringify(sel));
      // Add qty from purchased if available
      var p=purchasedOptions[layer]&&purchasedOptions[layer].find(function(x){return x.symbol===sel.symbol});
      if(p) item.qty=p.qty;
      selList[layer].push(item);
      localStorage.setItem('selectedOptions',JSON.stringify(selList));
      alert('Добавлен: '+sel.symbol);
    } else {
      alert('Уже добавлен: '+sel.symbol);
    }
    renderSelectedLayer(layer,purchasedOptions[layer]);
  } catch(e){ console.error('addSelected error:',e); }
}

function removeSelected(layer,index){
  var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
  if(selList[layer]){selList[layer].splice(index,1);localStorage.setItem('selectedOptions',JSON.stringify(selList));renderSelectedLayer(layer,purchasedOptions[layer]);}
}

function renderSelectedLayer(layer, purchased){
  var el=document.getElementById('selectedContent-'+layer);
  if(!el) return;
  var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
  var purchasedList=purchased||[];
  var purchMap={};
  purchasedList.forEach(function(p){purchMap[p.symbol]=p;});
  // Merge: keep local storage items + add purchased (no duplicates)
  var all=[];
  var seen={};
  selList[layer].forEach(function(s){if(!seen[s.symbol]){all.push(s);seen[s.symbol]=true;}});
  purchasedList.forEach(function(s){if(!seen[s.symbol]){all.push(s);seen[s.symbol]=true;}});
  var items=all;
  if(items.length===0){el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет выбранных</div>';return;}
  var html='<div style="max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:4px"><table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:var(--bg);border-bottom:1px solid var(--border)"><th style="text-align:left;padding:3px 4px">Символ</th><th style="padding:3px 4px;text-align:right">DTE</th><th style="padding:3px 4px;text-align:right">Qty</th><th style="padding:3px 4px;text-align:right">Price</th><th style="padding:3px 4px;text-align:right">Cost</th><th style="padding:3px 4px;text-align:right">Δ</th><th style="padding:3px 4px;text-align:right">Γ</th><th style="padding:3px 4px;text-align:right">Θ</th><th style="padding:3px 4px;text-align:center">Действия</th></tr></thead><tbody>';
  items.forEach(function(item,i){
    var purch=purchMap[item.symbol]||{};
    var s=item;
    var dte=+s.dte||'';
    var qty=s.qty!==undefined?s.qty:(purch.qty||1);
    var priceNum=+purch.entry_price||+s.price||0;
    var cost=(priceNum*qty).toFixed(2);
    var delta=s.delta!==undefined&&s.delta!==''?Number(s.delta).toFixed(4):'';
    var gamma=s.gamma!==undefined&&s.gamma!==''?Number(s.gamma).toFixed(4):'';
    var theta=s.theta!==undefined&&s.theta!==''?Number(s.theta).toFixed(4):'';
    html+='<tr><td style="padding:2px 4px;font-weight:bold">'+item.symbol+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+dte+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+qty+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+Number(priceNum).toFixed(4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+cost+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+delta+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+gamma+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+theta+'</td>';
    html+='<td style="padding:2px 4px;text-align:center"><button onclick="removeSelected(\''+layer+'\','+i+')" style="background:#d32f2f;color:#fff;border:none;padding:2px 6px;border-radius:4px;cursor:pointer;font-size:11px">✕</button></td></tr>';
  });
  html+='</tbody></table></div>';
  el.innerHTML=html;
}

function applyFilters(layer){
  var card=document.getElementById("tab-"+layer);
  if(!card) return;
  var inputs=card.querySelectorAll("input[type=number]");
  var p={};
  if(inputs[0]) p.delta_min=inputs[0].value;
  if(inputs[1]) p.delta_max=inputs[1].value;
  if(inputs[2]) p.dte_min=inputs[2].value;
  if(inputs[3]) p.dte_max=inputs[3].value;
  var qs=Object.keys(p).length?"?"+Object.entries(p).map(function(e){return e[0]+"="+e[1]}).join("&"):"";
  layerFilterParams[layer]=qs;
  api("/api/layer-"+layer+qs).then(function(data){renderLayer(data);renderSelectedLayer(layer,purchasedOptions[layer]);});
}

function resetFilters(layer){
  var card=document.getElementById("tab-"+layer);
  if(!card) return;
  var inputs=card.querySelectorAll("input[type=number]");
  var defs=layerDefaults[layer];
  if(inputs[0]) inputs[0].value=defs.delta_min;
  if(inputs[1]) inputs[1].value=defs.delta_max;
  if(inputs[2]) inputs[2].value=defs.dte_min;
  if(inputs[3]) inputs[3].value=defs.dte_max;
  var qs="?delta_min="+defs.delta_min+"&delta_max="+defs.delta_max+"&dte_min="+defs.dte_min+"&dte_max="+defs.dte_max;
  layerFilterParams[layer]=qs;
  api("/api/layer-"+layer+qs).then(function(data){renderLayer(data);renderSelectedLayer(layer,purchasedOptions[layer]);});
}

function refreshLayers(layer){
  var params=layerFilterParams[layer]?"?"+layerFilterParams[layer]:"";
  if(params&&!params.includes("refresh=1")) params+="&refresh=1";
  if(!params) params="?refresh=1";
  api("/api/layer-"+layer+params).then(function(data){renderLayer(data);renderSelectedLayer(layer,purchasedOptions[layer]);});
}

// === Load all ===
var combinedLadder=null;
function loadAll(){
  var distantQ=layerFilterParams.distant?"?"+layerFilterParams.distant:"";
  var midQ=layerFilterParams.mid?"?"+layerFilterParams.mid:"";
  var nearQ=layerFilterParams.near?"?"+layerFilterParams.near:"";
  Promise.all([
    api("/api/positions"),
    api("/api/options"),
    api("/api/recommendations"),
    api("/api/summary"),
    api("/api/layers"),
    api("/api/combined-ladder"),
    api("/api/layer-distant"+distantQ),
    api("/api/layer-mid"+midQ),
    api("/api/layer-near"+nearQ)
  ]).then(function(results){
    combinedLadder=results[5]||{ladder:[]};
    renderPositions(results[0]);
    renderOptions(results[1], results[0]);
    renderRecommendations(results[2]);
    renderSummary(results[3], results[1]);
    renderLayers(results[4]);
    layerData_distant=results[6];
    layerData_mid=results[7];
    layerData_near=results[8];
    api("/api/purchased-options").then(function(p){
      purchasedOptions={distant:p.distant||[],mid:p.mid||[],near:p.near||[]};
      renderLayer(results[6]);
      renderLayer(results[7]);
      renderLayer(results[8]);
      renderSelectedLayer('distant',purchasedOptions.distant);
      renderSelectedLayer('mid',purchasedOptions.mid);
      renderSelectedLayer('near',purchasedOptions.near);
    });
  });
  document.getElementById('headerUpdated').textContent='Обновлено: '+new Date().toLocaleTimeString('ru-RU');
}

loadAll();