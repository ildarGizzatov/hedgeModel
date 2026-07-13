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

// === Inline editing for entry_price ===
var editingCell = null;

function makeEditable(cell, currentValue, optionId, optionSymbol) {
  if (editingCell) cancelEdit();
  editingCell = cell;
  var input = document.createElement('input');
  input.type = 'number';
  input.step = '0.01';
  input.min = '0';
  input.style.width = '70px';
  input.style.background = 'var(--bg)';
  input.style.border = '2px solid var(--blue)';
  input.style.color = 'var(--text)';
  input.style.padding = '1px 4px';
  input.style.borderRadius = '3px';
  input.value = currentValue;
  cell.innerHTML = '';
  cell.appendChild(input);
  input.focus();
  input.select();

  var saveBtn = document.createElement('button');
  saveBtn.textContent = '✓';
  saveBtn.style.cssText = 'background:var(--green);color:#fff;border:none;padding:1px 6px;border-radius:3px;cursor:pointer;margin-left:3px;font-size:12px;';
  var cancelBtn = document.createElement('button');
  cancelBtn.textContent = '✕';
  cancelBtn.style.cssText = 'background:var(--red);color:#fff;border:none;padding:1px 6px;border-radius:3px;cursor:pointer;margin-left:2px;font-size:12px;';
  cell.appendChild(saveBtn);
  cell.appendChild(cancelBtn);

  function save() {
    var newVal = parseFloat(input.value);
    if (isNaN(newVal) || newVal <= 0) { alert('Введите корректную цену'); return; }
    fetch(API+'/api/update-option-entry', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({option_id: optionId, entry_price: newVal})
    }).then(function(r){ return r.json(); }).then(function(res) {
      if (res.status === 'ok') {
        cell.innerHTML = '<span style="color:var(--green)">$'+F(newVal,2)+'</span>';
        editingCell = null;
        loadAll();
      } else {
        alert('Ошибка: ' + res.output);
        cancelEdit();
      }
    }).catch(function(e) {
      alert('Ошибка: ' + e.message);
      cancelEdit();
    });
  }
  function cancel() { editingCell = null; cell.innerHTML = '$'+F(currentValue,2); }

  saveBtn.onclick = save;
  cancelBtn.onclick = cancel;
  input.onkeydown = function(e) {
    if (e.key === 'Enter') save();
    if (e.key === 'Escape') cancel();
  };
}

function cancelEdit() {
  if (!editingCell) return;
  var oldHtml = editingCell.getAttribute('data-old-html');
  if (oldHtml) editingCell.innerHTML = oldHtml;
  editingCell = null;
}

window.__closeOption = function(optionId, symbol, pnl) {
  var pnlStr = pnl >= 0 ? ('+' + F(pnl)) : '-' + F(Math.abs(pnl));
  if (!confirm('Закрыть ' + symbol + '\n\nPnL: ' + pnlStr + '\n\nТекущая цена будет взята из Greeks.')) return;
  fetch(API+'/api/close-option', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({option_id: optionId, close_reason: 'manual'})
  }).then(function(r){ return r.json(); }).then(function(res) {
    if (res.status === 'ok') {
      alert('✅ ' + res.message);
      loadAll();
    } else {
      alert('❌ ' + res.output);
    }
  }).catch(function(e) { alert('Ошибка: ' + e.message); });
};

var LAYER_CYCLE = ['anchor', 'adaptation', 'active'];
var LAYER_LABELS = {anchor: 'ANCHOR', adaptation: 'ADAPT', active: 'ACTIVE'};
var LAYER_COLORS = {anchor: 'var(--purple)', adaptation: 'var(--blue)', active: 'var(--yellow)'};
var _data_source = 'live';

window.__showBuyModal = function() {
  var modal = document.getElementById('buyModal');
  modal.style.display = 'flex';
  fetchBuyOptions();
};

function fetchBuyOptions() {
  var layer = document.getElementById('buyLayer').value;
  var defs = layerDefaults[layer] || {delta_min: 0.05, delta_max: 0.7, dte_min: 1, dte_max: 99999};
  fetch(API+'/api/buy-options?layer='+layer+'&delta_min='+defs.delta_min+'&delta_max='+defs.delta_max+'&dte_min='+defs.dte_min+'&dte_max='+defs.dte_max)
    .then(function(r){ return r.json(); })
    .then(function(res) {
      var el = document.getElementById('buyResult');
      if(!res.options || res.options.length === 0) {
        el.innerHTML = '<div style="padding:12px;color:var(--text-dim)">Нет доступных опционов</div>';
        return;
      }
      var html = '<table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border)"><th style="text-align:left;padding:3px 4px">Symbol</th><th style="padding:3px 4px;text-align:right">Strike</th><th style="padding:3px 4px;text-align:right">DTE</th><th style="padding:3px 4px;text-align:right">Δ</th><th style="padding:3px 4px;text-align:right">IV</th><th style="padding:3px 4px;text-align:right">Price</th><th style="padding:3px 4px;text-align:center">Действие</th></tr></thead><tbody>';
      res.options.forEach(function(o) {
        html+='<tr><td style="padding:2px 4px;font-weight:bold">'+o.symbol+'</td>';
        html+='<td style="padding:2px 4px;text-align:right">$'+o.strike+'</td>';
        html+='<td style="padding:2px 4px;text-align:right">'+o.dte+'</td>';
        html+='<td style="padding:2px 4px;text-align:right">'+F(o.delta,4)+'</td>';
        html+='<td style="padding:2px 4px;text-align:right">'+F(o.iv,4)+'</td>';
        html+='<td style="padding:2px 4px;text-align:right">$'+F(o.price,4)+'</td>';
        html+='<td style="padding:2px 4px;text-align:center"><button class="btn-buy" onclick="window.__buyOpt(\''+o.symbol+'\')">Купить</button></td></tr>';
      });
      html+='</tbody></table>';
      el.innerHTML = html;
    }).catch(function(e) { alert('Ошибка загрузки: '+e.message); });
}

window.__buyOpt = function(symbol) {
  var qty = parseInt(document.getElementById('buyQty').value) || 1;
  var layer = document.getElementById('buyLayer').value;
  fetch(API+'/api/buy-option', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol, qty: qty, layer: layer})
  }).then(function(r){ return r.json(); })
    .then(function(res) {
      if(res.status === 'ok') {
        alert('✅ Куплено: '+res.symbol+' | Price: $'+F(res.price,4)+' | Total: $'+res.total+' | ID: '+res.id);
        document.getElementById('buyModal').style.display = 'none';
        loadAll();
      } else {
        alert('❌ '+res.output);
      }
    }).catch(function(e) { alert('Ошибка: '+e.message); });
};

document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('buyLayer').addEventListener('change', fetchBuyOptions);
});

function cycleLayer(evt, optionId, currentLayer) {
  var cell = evt.target.closest('td');
  var idx = LAYER_CYCLE.indexOf(currentLayer);
  if (idx < 0) { alert('Неизвестный layer: ' + currentLayer); return; }
  var newLayer = LAYER_CYCLE[(idx + 1) % LAYER_CYCLE.length];
  fetch(API+'/api/update-option-layer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({option_id: optionId, layer: newLayer})
  }).then(function(r){ return r.json(); }).then(function(res) {
    if (res.status === 'ok') {
      cell.innerHTML = '<span class="layer-'+newLayer+'" style="cursor:pointer;font-weight:600" onclick="window.__cycleLayer(event,' + optionId + ',\'' + newLayer + '\')">'+LAYER_LABELS[newLayer]+'</span>';
      cell.setAttribute('title', 'Клик: ' + LAYER_LABELS[newLayer] + ' → ' + LAYER_LABELS[LAYER_CYCLE[(LAYER_CYCLE.indexOf(newLayer)+1)%3]]);
      loadAll();
    } else {
      alert('Ошибка: ' + res.output);
    }
  }).catch(function(e) { alert('Ошибка: ' + e.message); });
}

window.__cycleLayer = function(evt, optionId, currentLayer) {
  cycleLayer(evt, optionId, currentLayer);
};

window.__editPrice = function(evt, optionId, symbol, currentPrice) {
  var cell = evt.target.closest('td');
  makeEditable(cell, currentPrice, optionId, symbol);
};

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

// === DATA SOURCE BADGE ===
function updateDataSourceBadge(ds){
  if(ds === undefined || ds === null) ds = 'live';
  _data_source = ds;
  var badge = document.getElementById('ds-badge');
  if(!badge) return;
  var label, cls;
  if(ds==='live'){label='🟢 live';cls='ds-live';}
  else if(ds==='stale'){label='🟡 stale';cls='ds-stale';}
  else{label='🔴 offline';cls='ds-offline';}
  badge.className=cls;
  badge.textContent=label;
  // Banner
  var banner=document.getElementById('dataStatusBanner');
  if(!banner) return;
  if(ds==='offline'){
    banner.style.display='block';
    banner.style.background='rgba(248,81,73,.15)';
    banner.style.border='1px solid var(--red)';
    banner.style.borderRadius='6px';
    banner.style.padding='8px 16px';
    banner.style.fontSize='13px';
    banner.style.color='var(--red)';
    banner.innerHTML='⚠️ <b>Bybit недоступен</b> — показаны данные из кэша. Опционы могут не совпадать с реальностью.';
  } else if(ds==='stale'){
    banner.style.display='block';
    banner.style.background='rgba(210,153,34,.15)';
    banner.style.border='1px solid var(--yellow)';
    banner.style.borderRadius='6px';
    banner.style.padding='8px 16px';
    banner.style.fontSize='13px';
    banner.style.color='var(--yellow)';
    banner.innerHTML='⚠️ Данные обновляются с задержкой.';
  } else {
    banner.style.display='none';
  }
}

// === OPTION BOARD ===
function loadOptionBoard(){
  fetch(API+"/api/available-options")
    .then(function(r){return r.json();})
    .then(function(data){
      if(!data || !data.options || data.options.length===0){
        document.getElementById("optionBoard").innerHTML='<tr><td colspan="10" style="color:var(--text-dim);text-align:center">Нет данных</td></tr>';
        return;
      }
      var infoEl=document.getElementById("optionBoardInfo");
      if(infoEl){
        var src=data.data_source||"unknown";
        var age=data.data_age_minutes>=0?" («"+data.data_age_minutes+" мин назад»)":"";
        var spot=data.spot_price!=null?'Spot: $'+F(data.spot_price,2)+" | ":"";
        infoEl.textContent=spot+"Всего: "+data.count+" | Источник: "+src+age;
      }
      // Find closest strikes to spot price
      var spot=data.spot_price || 0;
      var strikes=[];
      var strikeSet={};
      data.options.forEach(function(o){
        var k=o.strike;
        if(!strikeSet[k]){strikeSet[k]=true;strikes.push(k);}
      });
      strikes.sort(function(a,b){return a-b;});
      var closest2=[];
      // Find strike index just below or equal to spot
      var idx=0;
      for(var i=0;i<strikes.length;i++){
        if(strikes[i]<=spot) idx=i;
      }
      if(idx<strikes.length) closest2.push(strikes[idx]);
      if(idx+1<strikes.length) closest2.push(strikes[idx+1]);
      var html="";
      data.options.forEach(function(o){
        var isClose=closest2.indexOf(o.strike)!==-1;
        var rowCls=isClose?' style="background:rgba(0,136,204,0.15);font-weight:700"':'';
        var strikeCell=isClose?'<b style="color:var(--blue)" title="Ближайший к spot">🎯 $'+F(o.strike,2)+'🎯</b>':'$'+F(o.strike,2);
        // Drop% = (spot - strike) / spot * 100
        var dropPct = spot > 0 ? Math.max(0, (spot - o.strike) / spot * 100) : 0;
        html+='<tr'+rowCls+'><td>'+o.symbol+'</td>';
        html+='<td>'+strikeCell+'</td>';
        html+='<td class="'+clr(-dropPct)+'">'+P(-dropPct)+'</td>';
        html+='<td>'+o.dte+'</td>';
        html+='<td>$'+F(o.price,2)+'</td>';
        html+='<td>'+F(o.delta,4)+'</td>';
        html+='<td>'+F(o.gamma,4)+'</td>';
        html+='<td>'+F(o.iv,4)+'</td>';
        html+='<td>'+F(o.theta,4)+'</td>';
        html+='</tr>';
      });
      document.getElementById("optionBoard").innerHTML=html;
    })
    .catch(function(e){
      document.getElementById("optionBoard").innerHTML='<tr><td colspan="10" style="color:var(--red);text-align:center">Ошибка: '+e.message+'</td></tr>';
    });
}

// === TAB 1: POSITIONS ===
function renderPositions(pos){
  posData = pos;
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
  var headerSpot=document.getElementById("headerSpot");
  if(headerSpot && pos.positions && pos.positions.length>0){
    var sol=pos.positions.find(function(p){return p.symbol==='SOL';});
    if(sol) headerSpot.textContent="SOL: $"+F(sol.current_price,2);
  }
  var rows="";
  pos.positions.forEach(function(p){
    var pc2=clr(p.pnl);
    var z=p.avg_price>p.current_price?'<span style="color:var(--red)">Просадка</span>':'<span style="color:var(--green)">Прибыль</span>';
    rows+='<tr style="font-size:15px"><td><b>'+p.symbol+'</b></td><td>'+F(p.qty,2)+'</td><td>$'+F(p.avg_price)+'</td><td>$'+F(p.current_price)+'</td><td class="'+pc2+'">'+U(p.pnl)+'</td><td class="'+pc2+'">'+P(p.pnl_pct)+'</td><td>'+z+'</td></tr>';
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
    var low25=Math.round(current*0.75);
    var rows="";
    for(var price=low25;price<=current;price++){
      var dPnl=(price-p.avg_price)*p.qty;
      var dPnlPct=((price-p.avg_price)/p.avg_price*100);
      var dropPct=((price-current)/current*100);
      var cls=clr(dPnl);
      var icon="";
      var rowBg="";
      var absDrop=Math.abs(dropPct);
      if(absDrop<=10){rowBg='background:rgba(210,153,34,.15)';}  // жёлтый
      else if(absDrop<=20){rowBg='background:rgba(30,80,220,.15)';}  // синий
      else{rowBg='background:rgba(46,204,113,.15)';}  // зелёный
      if(price===Math.round(current)) icon=" 🔵";
      else if(price===Math.round(p.avg_price)) icon=" 📍";
      else if(dPnl>=0) icon=" 🟢";
      else icon=" 🔴";
      rows+='<tr style="'+rowBg+'"><td class="'+cls+'">$'+price+icon+'</td>';
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
    optT.innerHTML='<tr><td colspan="13" style="color:var(--red);text-align:center">Ошибка загрузки</td></tr>';
    return;
  }
  var t=opt.totals;
  var rows="";
  opt.options.forEach(function(o){
    var pc2=clr(o.pnl);
    var ivClr=o.iv_change>=0?"green":"red";
    var symEsc=o.symbol.replace(/'/g,"\'");
    rows+='<tr style="text-align:left">';
    rows+='<td>'+o.symbol+'</td>';
    var layerDisplay = o.layer && LAYER_LABELS[o.layer] ? LAYER_LABELS[o.layer] : (o.layer || '—').toUpperCase();
    var nextLayer = o.layer && LAYER_CYCLE.indexOf(o.layer) >= 0 ? LAYER_LABELS[LAYER_CYCLE[(LAYER_CYCLE.indexOf(o.layer)+1)%3]] : '';
    rows+='<td class="layer-'+(o.layer||'')+'" style="cursor:pointer;font-weight:600" onclick="window.__cycleLayer(event,' + o.id + ',\'' + (o.layer||'anchor') + '\')" title="Клик: '+layerDisplay+' → '+nextLayer+'">'+layerDisplay+'</td>';
    rows+='<td>'+o.dte+'</td>';
    rows+='<td>'+o.qty+'</td>';
    rows+='<td>$'+o.strike+'</td>';
    rows+='<td style="cursor:pointer" onclick="window.__editPrice(event,' + o.id + ',\'' + symEsc + '\',' + o.entry_price + ')" title="Клик: редактировать цену">$'+F(o.entry_price,2)+'</td>';
    rows+='<td>$'+F(o.current_price,2)+'</td>';
    rows+='<td class="'+pc2+'">'+U(o.pnl)+'</td>';
    rows+='<td title="Entry: '+F(o.delta_entry,4)+'\nИзменение: '+F(o.delta_change,4)+'">'+F(o.delta,4)+'</td>';
    rows+='<td title="Entry: '+F(o.gamma_entry,4)+'\nИзменение: '+F(o.gamma_change,4)+'">'+F(o.gamma,4)+'</td>';
    rows+='<td class="'+pc2+'" title="Entry: '+F(o.theta_entry,4)+'\nНа день: '+F(o.theta_per_day,4)+'">'+F(o.theta_per_day,4)+'</td>';
    rows+='<td title="Entry: '+F(o.iv_entry,4)+'\nТекущий IV: '+F(o.iv,4)+'">'+F(o.iv,4)+'</td>';
    rows+='<td class="'+ivClr+'" title="Входной IV: '+F(o.iv_entry,4)+'\nТекущий IV: '+F(o.iv,4)+'\nИзменение: '+F(o.iv_change,4)+'">'+F(o.iv_change,4)+'</td>';
    rows+='<td><button class="btn-close" onclick="window.__closeOption(' + o.id + ',\'' + symEsc + '\', ' + o.pnl + ')" title="Закрыть опцион">✕</button></td>';
    rows+='</tr>';
  });
  optT.innerHTML=rows;
  // Net Greeks — итоговая строка внизу таблицы
  var tEl=document.getElementById("optTable");
  if(tEl){
    tEl.insertAdjacentHTML("beforeend",
      '<tr style="background:var(--surface);border-top:2px solid var(--border);font-weight:700"><td colspan="4" style="color:var(--blue);font-size:15px">Итого</td><td></td><td></td><td></td><td style="'+clr(t.total_pnl)+';font-size:15px">'+U(t.total_pnl)+'</td><td style="font-size:15px">'+F(t.net_delta,4)+'</td><td style="font-size:15px">'+F(t.net_gamma,4)+'</td><td style="font-size:15px">'+F(t.net_theta,4)+'</td><td></td><td></td></tr>');
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

  // Set ladder range inputs (default ±20% from avg)
  if(sum.assets && sum.assets.total_cost > 0 && posData && posData.positions && posData.positions.length > 0){
    var avgP = posData.positions[0].avg_price;
    var defMin = Math.round(avgP * 0.8);
    var defMax = Math.round(avgP * 1.2);
    var minInput = document.getElementById("ladderMin");
    var maxInput = document.getElementById("ladderMax");
    if(minInput && maxInput){
      if(!minInput.value) minInput.value = defMin;
      if(!maxInput.value) maxInput.value = defMax;
    }
  }
}

function updateLadderRange(){
  var minInput = document.getElementById("ladderMin");
  var maxInput = document.getElementById("ladderMax");
  if(!minInput || !maxInput) { alert('Поля не найдены'); return; }
  var minVal = parseInt(minInput.value);
  var maxVal = parseInt(maxInput.value);
  if(isNaN(minVal) || isNaN(maxVal)){ alert('Введите числа'); return; }
  fetch(API + "/api/combined-ladder?min_price=" + minVal + "&max_price=" + maxVal)
    .then(function(r){ return r.json(); })
    .then(function(comb){
      if(!comb || !comb.ladder){ alert('Нет данных'); return; }
      combinedLadder = comb;
      renderPnnLadderTable(posData || {});
    })
    .catch(function(e){ alert('Ошибка: '+e.message); });
}

function resetLadderRange(){
  var minInput = document.getElementById("ladderMin");
  var maxInput = document.getElementById("ladderMax");
  if(!minInput || !maxInput) return;
  api("/api/positions").then(function(pos){
    if(pos && pos.positions && pos.positions.length > 0){
      var avgP = pos.positions[0].avg_price;
      minInput.value = Math.round(avgP * 0.8);
      maxInput.value = Math.round(avgP * 1.2);
      updateLadderRange();
    }
  });
}

function renderPnnLadderTable(posData){
  var ladderEl = document.getElementById("posLadder");
  if(!ladderEl || !combinedLadder || !combinedLadder.ladder) return;
  var solPnlMap = {};
  (posData.pnl_ladder || []).forEach(function(row){ solPnlMap[row.price] = row.pnl; });
  var html = "";
  combinedLadder.ladder.forEach(function(row){
    var cls = row.is_current ? "color:var(--blue);font-weight:700" : clr(row.total_pnl);
    var icon = row.is_current ? " 🔵" : (row.is_avg ? " 📍" : (row.total_pnl >= 0 ? " 🟢" : " 🔴"));
    // row содержит sol_pnl, opt_pnl, total_pnl из API
    var solPnl = row.sol_pnl || solPnlMap[row.price] || 0;
    var optPnl = row.opt_pnl || (row.total_pnl - solPnl);
    var intrinsic = row.intrinsic_value || 0;
    html += '<tr><td class="'+cls+'">$'+row.price+icon+'</td>';
    html += '<td class="'+cls+'">'+P(row.total_pnl_pct)+'</td>';
    html += '<td class="'+cls+'">'+U(solPnl)+'</td>';
    html += '<td class="'+cls+'">'+U(row.total_pnl)+'</td>';
    html += '<td class="'+clr(optPnl)+'">'+U(optPnl)+'</td>';
    html += '<td class="'+clr(intrinsic)+'">'+U(intrinsic)+'</td></tr>';
  });
  ladderEl.innerHTML = html;
}

// Keep global posData reference for renderPnnLadderTable
var posData = null;

// === LAYER TABS ===
var layerFilterParams={distant:"all=1",mid:"all=1",near:"all=1"};
var selectedOption={distant:[],mid:[],near:[]};


var layerDefaults={distant:{delta_min:0.05,delta_max:0.20,dte_min:25,dte_max:99999},mid:{delta_min:0.20,delta_max:0.40,dte_min:10,dte_max:25},near:{delta_min:0.25,delta_max:0.45,dte_min:5,dte_max:25}};
var purchasedOptions={distant:[],mid:[],near:[]};
var globalPurchasedSymbols={};

window.__so = function(layer,symbol){
  selectOption(layer,symbol);
};

window.__as = function(layer,symbol){
  // Double-click: add to selectedOption array
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
    selectedOption[layer].push({symbol:symbol, strike:found.strike, dte:found.dte, iv:found.iv, price:found.price, delta:found.delta, gamma:found.gamma, theta:found.theta, vega:found.vega, spot_at_entry:found.spot_price, spot_price:found.spot_price});
  } else {
    selectedOption[layer].push({symbol:symbol});
  }
  console.log('__as: selectedOption='+JSON.stringify(selectedOption[layer]));
  addSelected(layer,symbol);
  
  // Create dynamic sub-tab for this option
  if(found && layer==='near') {
    createOptionTab(layer, found);
    createAggregatorTab(layer);
  }
};

function renderLayer(data){
  if(!data) return;
  var layer=data.layer;
  var el=document.getElementById("layerContent-"+layer);
  var t=document.getElementById("layerTitle-"+layer);
  if(!el) return;
  // Don't overwrite static HTML headers
  // if(t) t.textContent=data.label;
  var spot=data.spot_price||0;
  // Hedging range: % drop from spot
  var hedges={near:{min:3,max:10},mid:{min:8,max:15},distant:{min:15,max:30}};
  var h=hedges[layer]||{min:5,max:20};
  var lowStrike=spot*(1-h.max/100);
  var highStrike=spot*(1-h.min/100);
  var html='<div style="margin-bottom:8px;font-size:15px;font-weight:bold">Хедж: '+h.min+'–'+h.max+'% просадка | Strike $'+F(lowStrike,1)+'–$'+F(highStrike,1)+' | Всего: <b>'+data.count+'</b></div>';
  var opts=data.options||[];
  if(opts.length===0){html+='<div style="padding:12px;color:var(--text-dim)">Нет опционов</div>';el.innerHTML=html;return;}
  // Sort by layer type
  opts.sort(function(a,b){
    if(layer==='near'){
      if(Math.abs(a.delta)-Math.abs(b.delta)>0.0001) return Math.abs(b.delta)-Math.abs(a.delta);
      return a.dte-b.dte;
    }
    // distant and mid: DTE desc, delta asc
    if(a.dte-b.dte!==0) return b.dte-a.dte;
    return Math.abs(a.delta)-Math.abs(b.delta);
  });
  // Find closest strikes to spot price
  var spot=data.spot_price || 0;
  var strikes=[];
  var strikeSet={};
  opts.forEach(function(o){
    var k=o.strike;
    if(!strikeSet[k]){strikeSet[k]=true;strikes.push(k);}
  });
  strikes.sort(function(a,b){return a-b;});
  var closest2=[];
  var idx=0;
  for(var i=0;i<strikes.length;i++){
    if(strikes[i]<=spot) idx=i;
  }
  if(idx<strikes.length) closest2.push(strikes[idx]);
  if(idx+1<strikes.length) closest2.push(strikes[idx+1]);
  // Build purchased symbols lookup
  var purchSymbols={};
  (purchasedOptions[layer]||[]).forEach(function(p){purchSymbols[p.symbol]=p.qty;});
  
  html+='<div style="max-height:400px;overflow-y:auto;border:1px solid var(--border);border-radius:4px"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:3px 6px">Символ</th><th style="padding:3px 6px;text-align:center">Drop%</th><th style="padding:3px 6px;text-align:right">Strike</th><th style="padding:3px 6px;text-align:center">DTE</th><th style="padding:3px 6px;text-align:right">Premium</th><th style="padding:3px 6px;text-align:right">Δ</th><th style="padding:3px 6px;text-align:right">Γ</th><th style="padding:3px 6px;text-align:right">Θ</th><th style="padding:3px 6px;text-align:right">IV</th><th style="padding:3px 6px;text-align:right">OI</th><th style="padding:3px 6px;text-align:right">Volume</th><th style="padding:3px 6px;text-align:right">Spread</th></tr></thead><tbody>';
  opts.forEach(function(o){
    var rowCls="";
    var sym=o.symbol.replace(/'/g,"\\'");
    var dropPct=spot>0?((spot-o.strike)/spot*100):0;
    var dropCls=dropPct>=0?'color:var(--green)':'color:#d32f2f';
    var dropStr=(dropPct>=0?'+':'')+F(dropPct,2)+'%';
    var title='Один клик: выделить, двойной: добавить | IV ATM: '+F(o.iv_atm,4);
    var purchased=purchSymbols[o.symbol];
    if(purchased) title+=' | 📌 Куплено: '+purchased;
    html+='<tr style="text-align:left;height:24px;cursor:pointer;'+rowCls+' onclick="window.__so(\''+layer+'\',\''+sym+'\')" ondblclick="event.preventDefault();event.stopPropagation();window.__as(\''+layer+'\',\''+sym+'\')" title="'+title+'">';
    html+='<td style="padding:2px 6px;font-weight:bold">'+o.symbol+(purchased?'<span style="color:#f0ad4e">📌'+purchased+'</span>':'')+'</td>';
    html+='<td style="padding:2px 6px;text-align:center;color:'+dropCls+'"><b>'+dropStr+'</b></td>';
    var strikeCell='';
    if(closest2.indexOf(o.strike)!==-1){strikeCell='<b style="color:var(--blue)" title="Ближайший к spot">🎯 $'+o.strike+'</b>';}else{strikeCell='$'+o.strike;}
    html+='<td style="padding:2px 6px;text-align:right">'+strikeCell+'</td>';
    html+='<td style="padding:2px 6px;text-align:center">'+o.dte+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(o.price,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.delta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.gamma,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.theta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.iv,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+(o.open_interest||0)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+(o.volume||o.open_interest||0)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+(o.spread||'—')+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  el.innerHTML=html;
}

function selectOption(layer,symbol,o){
  try {
    if(o){
      selectedOption[layer].push({symbol:symbol, strike:o.strike, dte:o.dte, iv:o.iv, price:o.price, delta:o.delta, gamma:o.gamma, theta:o.theta, vega:o.vega, spot_at_entry:o.spot_price});
    } else if(layerData_distant&&layerData_distant.options&&layer==='distant'){
      var f=layerData_distant.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer].push(f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega, spot_at_entry:f.spot_price}:{symbol:symbol});
    } else if(layerData_mid&&layerData_mid.options&&layer==='mid'){
      var f=layerData_mid.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer].push(f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega, spot_at_entry:f.spot_price}:{symbol:symbol});
    } else if(layerData_near&&layerData_near.options&&layer==='near'){
      var f=layerData_near.options.find(function(x){return x.symbol===symbol});
      selectedOption[layer].push(f?{symbol:symbol, strike:f.strike, dte:f.dte, iv:f.iv, price:f.price, delta:f.delta, gamma:f.gamma, theta:f.theta, vega:f.vega, spot_at_entry:f.spot_price}:{symbol:symbol});
    } else {
      selectedOption[layer].push({symbol:symbol});
    }
    console.log('selectOption:', layer, selectedOption[layer]);
  } catch(e){ console.error('selectOption error:',e); }
  var params=layerFilterParams[layer]?"?"+layerFilterParams[layer]:"";
  api("/api/layer/"+layer+params).then(function(d){renderLayer(d);});
}

function addSelected(layer,symbol){
  try {
    var selArr=selectedOption[layer];
    if(!selArr||!selArr.length){alert('Сначала кликните на опцион');return;}
    var sel=selArr[selArr.length-1];
    var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
    if(!selList[layer]) selList[layer]=[];
    if(!selList[layer].find(function(x){return x.symbol===sel.symbol})){
      var item=JSON.parse(JSON.stringify(sel));
      item.qty=1;
      selList[layer].push(item);
      localStorage.setItem('selectedOptions',JSON.stringify(selList));
      alert('Добавлен: '+sel.symbol);
    } else {
      alert('Уже добавлен: '+sel.symbol);
    }
  } catch(e){ console.error('addSelected error:',e); }
}

function removeOptionTab(symbol){
  // Find and remove from selectedOption in all layers
  var foundLayer=null;
  for(var lay in selectedOption){
    for(var i=0;i<selectedOption[lay].length;i++){
      if(selectedOption[lay][i].symbol===symbol){
        selectedOption[lay].splice(i,1);
        foundLayer=lay;
        break;
      }
    }
  }
  
  var btn=document.querySelector('[data-opttab="'+symbol+'"]');
  if(btn) btn.remove();
  var content=document.getElementById('content-'+symbol);
  if(content) content.remove();
  
  // Re-render aggregator if it exists
  if(foundLayer){
    var aggBtn=document.querySelector('[data-opttab="aggregator"]');
    var aggContent=document.getElementById('content-aggregator');
    if(aggBtn && aggContent) renderAggregatorGreeks(foundLayer);
  }
  
  // If no tabs left, show a message
  if(document.querySelectorAll('[data-opttab]').length===0){
    var msg=document.getElementById('dynamicOptionContent');
    if(msg) msg.innerHTML='';
  } else {
    // Activate first remaining tab
    var first=document.querySelector('[data-opttab]');
    if(first){
      first.classList.add('active');
      first.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--blue);margin-bottom:-2px;color:var(--blue);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
      var firstId=first.getAttribute('data-opttab');var fc=document.getElementById('content-'+firstId);if(fc)fc.style.display='flex';
    }
  }
}

function createOptionTab(layer, opt){
  // Check if tab already exists
  if(document.getElementById('content-'+opt.symbol)) return;
  
  var tabBar=document.getElementById('dynamicOptionTabs');
  var contentArea=document.getElementById('dynamicOptionContent');
  
  // Create tab button
  var btn=document.createElement('div');
  btn.className='layer-subtab';
  btn.setAttribute('data-opttab', opt.symbol);
  btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
  var label=document.createElement('span');
  label.textContent=opt.symbol;
  label.style.cssText='overflow:hidden;text-overflow:ellipsis;max-width:180px;';
  var xbtn=document.createElement('span');
  xbtn.textContent='✕';
  xbtn.style.cssText='cursor:pointer;color:var(--text-dim);font-size:14px;line-height:1;';
  xbtn.onclick=function(e){e.stopPropagation();removeOptionTab(opt.symbol);};
  btn.appendChild(label);
  btn.appendChild(xbtn);
  btn.onclick=function(){
    document.querySelectorAll('[data-opttab]').forEach(function(t){
      t.classList.remove('active');
      t.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
    });
    btn.classList.add('active');
    btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--blue);margin-bottom:-2px;color:var(--blue);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
    document.querySelectorAll('.option-content').forEach(function(c){c.style.display='none';});
    document.getElementById('content-'+opt.symbol).style.display='flex';
  };
  tabBar.appendChild(btn);
  
  // Create content div
  var content=document.createElement('div');
  content.className='option-content';
  content.id='content-'+opt.symbol;
  content.style.cssText='margin-top:8px;';
  content.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Загрузка...</div>';
  contentArea.appendChild(content);
  
  // Activate first tab
  if(document.querySelectorAll('[data-opttab]').length===1){
    btn.classList.add('active');
    btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--blue);margin-bottom:-2px;color:var(--blue);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
    content.style.display='flex';
  }
  
  // Fetch BS Greeks
  api('/api/bs-greeks?symbol='+encodeURIComponent(opt.symbol)+'&strike='+opt.strike+'&dte='+opt.dte+'&iv='+opt.iv+'&spot='+opt.spot_price+'&premium='+opt.price+'&layer='+layer)
    .then(function(d){renderOptionGreeks(d, layer);})
    .catch(function(e){
      content.innerHTML='<div style="color:#d32f2f;padding:12px;text-align:center">Ошибка: '+e+'</div>';
    });
}

var aggregatorCache={};

function createAggregatorTab(layer){
  var tabBar=document.getElementById('dynamicOptionTabs');
  var contentArea=document.getElementById('dynamicOptionContent');
  
  // Create tab button if not exists
  var btn=document.querySelector('[data-opttab="aggregator"]');
  if(!btn){
    btn=document.createElement('div');
    btn.className='layer-subtab';
    btn.setAttribute('data-opttab', 'aggregator');
    btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;background:rgba(139,92,246,0.15);';
    var label=document.createElement('span');
    label.textContent='📊 Суммарный';
    label.style.cssText='overflow:hidden;text-overflow:ellipsis;';
    var xbtn=document.createElement('span');
    xbtn.textContent='✕';
    xbtn.style.cssText='cursor:pointer;color:var(--text-dim);font-size:14px;line-height:1;';
    xbtn.onclick=function(e){e.stopPropagation();removeAggregatorTab();};
    btn.appendChild(label);
    btn.appendChild(xbtn);
    btn.onclick=function(){
      document.querySelectorAll('[data-opttab]').forEach(function(t){
        t.classList.remove('active');
        t.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
      });
      btn.classList.add('active');
      btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--purple);margin-bottom:-2px;color:#a78bfa;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;background:rgba(139,92,246,0.2);';
      document.querySelectorAll('.option-content').forEach(function(c){c.style.display='none';});
      document.getElementById('content-aggregator').style.display='flex';
    };
    // Insert aggregator tab at END (after all option tabs)
    var lastTab=tabBar.querySelector('[data-opttab]');
    if(lastTab) tabBar.insertBefore(btn, lastTab.nextSibling);
    else tabBar.appendChild(btn);
  }
  
  // Create content div if not exists
  var content=document.getElementById('content-aggregator');
  if(!content){
    content=document.createElement('div');
    content.className='option-content';
    content.id='content-aggregator';
    content.style.cssText='margin-top:8px;';
    content.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Выберите опционы двойным кликом</div>';
    contentArea.appendChild(content);
  }
  
  // Activate aggregator tab
  btn.classList.add('active');
  btn.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--purple);margin-bottom:-2px;color:#a78bfa;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;background:rgba(139,92,246,0.2);';
  document.querySelectorAll('[data-opttab]').forEach(function(t){
    if(t!==btn){
      t.classList.remove('active');
      t.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid transparent;margin-bottom:-2px;color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
    }
  });
  document.querySelectorAll('.option-content').forEach(function(c){c.style.display='none';});
  content.style.display='flex';
  
  // Render aggregator
  renderAggregatorGreeks(layer);
}

function removeAggregatorTab(){
  var btn=document.querySelector('[data-opttab="aggregator"]');
  if(btn) btn.remove();
  var content=document.getElementById('content-aggregator');
  if(content) content.remove();
  aggregatorCache={};
  if(document.querySelectorAll('[data-opttab]').length===0){
    var msg=document.getElementById('dynamicOptionContent');
    if(msg) msg.innerHTML='';
  } else {
    var first=document.querySelector('[data-opttab]');
    if(first){
      first.classList.add('active');
      first.style.cssText='padding:4px 8px;cursor:pointer;font-weight:bold;border-bottom:2px solid var(--blue);margin-bottom:-2px;color:var(--blue);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px;';
      var firstId=first.getAttribute('data-opttab');var fc=document.getElementById('content-'+firstId);if(fc)fc.style.display='flex';
    }
  }
}

function renderAggregatorGreeks(layer){
  layer=layer||'near';
  var sel=selectedOption[layer]||[];
  if(sel.length===0){
    var el=document.getElementById('content-aggregator');
    if(el) el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет выбранных опционов</div>';
    return;
  }
  
  var el=document.getElementById('content-aggregator');
  el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Загрузка...</div>';
  
  // Fetch BS for each selected option
  console.log('renderAggregatorGreeks: selected options:', sel.length, sel);
  if(sel.length===0){return;}
  var promises=sel.map(function(opt){
    var spot=opt.spot_price||opt.spot_at_entry||'';
    if(!spot){console.warn('No spot for',opt.symbol);return Promise.resolve(null);}
    var url='/api/bs-greeks?symbol='+encodeURIComponent(opt.symbol)+'&strike='+opt.strike+'&dte='+opt.dte+'&iv='+opt.iv+'&spot='+spot+'&premium='+opt.price+'&layer='+layer;
    console.log('API call:', url);
    return api(url)
      .then(function(d){console.log('OK',opt.symbol,d.rows?d.rows.length:'NO_ROWS','rows');return d;})
      .catch(function(e){console.error('ERR',opt.symbol,e);return null;});
  });
  
  Promise.all(promises).then(function(results){
  console.log('All results:', results.map(function(r){return r?r.symbol:'NULL';}));
    var validResults=results.filter(function(r){return r&&r.rows&&r.rows.length>0;});
    if(validResults.length===0){
      el.innerHTML='<div style="color:#d32f2f;padding:12px;text-align:center">Не удалось загрузить данные</div>';
      return;
    }
    
    // Aggregate all rows by price
    var priceMap={};
    var spot=validResults[0].spot||validResults[0].rows[0].price;
    var allStrikes=[];
    var allHedgeRanges=[];
    
    validResults.forEach(function(d){
      allStrikes.push(d.strike);
      allHedgeRanges.push(d.hedge_range);
      
      d.rows.forEach(function(r){
        if(!priceMap[r.price]){
          priceMap[r.price]={price:r.price, delta:0, gamma:0, theta:0, vega:0, bs_price:0, count:0};
        }
        priceMap[r.price].delta+=r.delta;
        priceMap[r.price].gamma+=r.gamma;
        priceMap[r.price].theta+=r.theta;
        priceMap[r.price].vega+=r.vega;
        priceMap[r.price].bs_price+=r.bs_price;
        priceMap[r.price].count++;
      });
    });
    
    // Sort by price
    var aggregated=Object.values(priceMap).sort(function(a,b){return b.price-a.price;});
    
    // Filter to working window (aggregate filtered ranges)
    var aggFiltered=[];
    aggregated.forEach(function(r){
      var absD=Math.abs(r.delta);
      if(absD >= 0.5 && absD <= 0.85){
        aggFiltered.push(r);
      }
    });
    
    // Filter to hedge range ± 2 steps
    var displayStart=avgHedgeLow-2, displayEnd=avgHedgeHigh+2;
    var displayRows=aggregated.filter(function(r){return r.price>=displayStart && r.price<=displayEnd;});
    
    // Find max gamma within display rows
    var maxGamma=-1;
    displayRows.forEach(function(r){
      if(r.gamma>maxGamma){maxGamma=r.gamma;}
    });
    
    // Map display index to find max gamma highlight
    var maxGammaPrice=-1;
    displayRows.forEach(function(r){
      if(Math.abs(r.gamma-maxGamma)<0.000001 && maxGammaPrice===-1){maxGammaPrice=r.price;}
    });
    
    // Average hedge range
    var avgHedgeLow=0, avgHedgeHigh=0;
    allHedgeRanges.forEach(function(hr){
      avgHedgeLow+=hr.low;
      avgHedgeHigh+=hr.high;
    });
    avgHedgeLow=Math.round(avgHedgeLow/allHedgeRanges.length);
    avgHedgeHigh=Math.round(avgHedgeHigh/allHedgeRanges.length);
    
    // Coverage calc
    var priceDelta50=aggFiltered.length>0?aggFiltered[0].price:0;
    var priceDelta85=aggFiltered.length>0?aggFiltered[aggFiltered.length-1].price:0;
    var windowLen=Math.round(Math.abs(priceDelta50-priceDelta85));
    var hedgeLen=Math.abs(avgHedgeHigh-avgHedgeLow);
    var overlapLow=Math.max(priceDelta85, avgHedgeLow);
    var overlapHigh=Math.min(priceDelta50, avgHedgeHigh);
    var overlapLen=Math.max(0, overlapHigh-overlapLow);
    var coverage=hedgeLen>0?overlapLen/hedgeLen:0;
    var accuracy=windowLen>0?overlapLen/windowLen:0;
    
    // Sum delta delta
    var sumDeltaDD=0;
    for(var i=1;i<aggFiltered.length;i++){
      if(aggFiltered[i].price>=overlapLow && aggFiltered[i].price<=overlapHigh){
        sumDeltaDD+=aggFiltered[i-1].delta-aggFiltered[i].delta;
      }
    }
    
    // Compute summary Greeks (sum of all selected options' Greeks)
    var totalDelta=0, totalGamma=0, totalTheta=0, totalVega=0;
    var totalPnl=0;
    sel.forEach(function(s){
      totalDelta+=s.delta||0;
      totalGamma+=s.gamma||0;
      totalTheta+=s.theta||0;
      totalVega+=s.vega||0;
      var entryP=s.entry_price||s.price||0;
      var curP=s.price||entryP;
      totalPnl+=(curP-entryP)*100*(s.qty||1);
    });
    var avgStrike=Math.round(allStrikes.reduce(function(a,b){return a+b;},0)/allStrikes.length);
    
    // Filter to hedge range ± 2 steps
    var displayStart=avgHedgeLow-2, displayEnd=avgHedgeHigh+2;
    var displayRows=aggregated.filter(function(r){return r.price>=displayStart && r.price<=displayEnd;});
    
    // Find max gamma within display rows
    var maxGamma=-1;
    displayRows.forEach(function(r){
      if(r.gamma>maxGamma){maxGamma=r.gamma;}
    });
    
    // Map display index to find max gamma highlight
    var maxGammaPrice=-1;
    displayRows.forEach(function(r){
      if(Math.abs(r.gamma-maxGamma)<0.000001 && maxGammaPrice===-1){maxGammaPrice=r.price;}
    });
    
    // Build price-based table (like individual tabs)
    var html='<div style="display:flex;gap:24px;align-items:flex-start">';
    html+='<div style="max-height:400px;overflow-y:auto;border:1px solid var(--border);border-radius:6px"><table style="width:auto;border-collapse:collapse;font-size:11px;font-weight:600"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
    html+='<th style="text-align:left;padding:3px 4px;font-size:11px">Цена</th>';
    html+='<th style="padding:3px 4px;text-align:right;font-size:11px">ΣΔ</th>';
    html+='<th style="padding:3px 4px;text-align:right;font-size:11px">ΣΓ</th>';
    html+='<th style="padding:3px 4px;text-align:right;font-size:11px">PnL</th>';
    html+='<th style="padding:3px 4px;text-align:right;font-size:11px">Вн.стоимость</th>';
    html+='<th style="padding:3px 4px;text-align:right;font-size:11px">Врем.стоимость</th>';
    html+='</tr></thead><tbody>';
    
    var avgEntry=sel.reduce(function(a,s){return a+(s.entry_price||s.price||0);},0)/sel.length;
    displayRows.forEach(function(r){
      var pnl=r.bs_price-avgEntry;
      var pnlCls=pnl>=0?'color:var(--green)':'color:var(--red)';
      
      var rowBg='';
      if(r.price===maxGammaPrice) rowBg='background:rgba(88,166,255,0.15);';
      if(r.price>=avgHedgeLow && r.price<=avgHedgeHigh){
        rowBg+='background:rgba(63,185,80,0.15);';
      }
      
      var intrinsic=Math.max(0, avgStrike-r.price);
      var timeValue=r.bs_price-intrinsic;
      var tvCls=timeValue>=0?'color:var(--green)':'color:var(--red)';
      var intrinsicCls=intrinsic>0?'color:var(--green)':'color:var(--text-dim)';
      
      html+='<tr style="text-align:left;height:28px;'+rowBg+'">' ;
      html+='<td style="padding:2px 4px;font-weight:bold">$'+r.price+'</td>';
      html+='<td style="padding:2px 4px;text-align:right">'+F(r.delta,4)+'</td>';
      html+='<td style="padding:2px 4px;text-align:right">'+F(r.gamma,6)+'</td>';
      html+='<td style="padding:2px 4px;text-align:right;'+pnlCls+'">'+F(pnl,2)+'</td>';
      html+='<td style="padding:2px 4px;text-align:right;'+intrinsicCls+'">'+F(intrinsic,2)+'</td>';
      html+='<td style="padding:2px 4px;text-align:right;'+tvCls+'">'+F(timeValue,2)+'</td>';
      html+='</tr>';
    });
    html+='</tbody></table></div>';
    
    // Gamma chart
    html+='<div style="min-width:580px;flex-shrink:0"><div style="font-size:14px;font-weight:bold;margin-bottom:6px;color:var(--text-dim)">Суммарный Γ</div><div style="border:1px solid var(--border);border-radius:6px;padding:8px;background:var(--surface)"><canvas id="gammaChart-aggregator" width="580" height="380"></canvas></div></div>';
    html+='</div>';
    
    el.innerHTML=html;
    
    // Draw aggregator chart
    setTimeout(function(){
      drawGammaChart(displayRows, displayRows, avgStrike, avgHedgeLow, avgHedgeHigh, 'gammaChart-aggregator', validResults);
      var c=document.getElementById('gammaChart-aggregator');
      if(c) console.log('aggregator chart drawn:', c.width, 'x', c.height);
    }, 50);
  });
}

function drawGammaChart(allRows, filtered, strike, hedgeLow, hedgeHigh, chartId, extraProfiles){
  extraProfiles=extraProfiles||[];
  if(!chartId) chartId='gammaChart';
  console.log('drawGammaChart called:', allRows.length, 'rows, strike=', strike, 'hedge=[', hedgeLow, hedgeHigh, ']');
  var canvas=document.getElementById(chartId);
  if(!canvas) { console.log('gammaChart canvas NOT FOUND'); return; }
  console.log('gammaChart '+chartId+':', canvas.width, 'x', canvas.height);
  var ctx=canvas.getContext('2d');
  var W=canvas.width, H=canvas.height;
  var pad={t:25,r:20,b:60,l:55};
  var cW=W-pad.l-pad.r, cH=H-pad.t-pad.b;
  
  ctx.clearRect(0,0,W,H);
  
  // Find price range - expand 20% on each side
  var prices=allRows.map(function(r){return r.price;});
  var pMin=Math.min.apply(null,prices);
  var pMax=Math.max.apply(null,prices);
  var pRange=pMax-pMin;
  var xMin=pMin-pRange*0.15;
  var xMax=pMax+pRange*0.15;
  var xRange=xMax-xMin;
  
  // Find gamma range (all positive for puts)
  var gammas=allRows.map(function(r){return r.gamma;});
  var gMax=Math.max.apply(null,gammas)*1.1;
  var gMin=0;
  var gRange=gMax-gMin;
  
  function toX(p){return pad.l+(p-xMin)/xRange*cW;}
  function toY(g){return pad.t+cH-(g-gMin)/gRange*cH;}
  
  // Background
  ctx.fillStyle='#0d1117';
  ctx.fillRect(0,0,W,H);
  
  // Grid lines
  ctx.strokeStyle='#21262d';
  ctx.lineWidth=1;
  for(var i=0;i<=5;i++){
    var y=pad.t+cH*(i/5);
    ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(pad.l+cW,y);ctx.stroke();
  }
  for(var i=0;i<=5;i++){
    var x=pad.l+cW*(i/5);
    ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,pad.t+cH);ctx.stroke();
  }
  
  // Hedge range zone
  if(hedgeLow && hedgeHigh){
    var hx1=toX(hedgeLow),hx2=toX(hedgeHigh);
    ctx.fillStyle='rgba(63,185,80,0.08)';
    ctx.fillRect(hx1,pad.t,hx2-hx1,cH);
    ctx.strokeStyle='rgba(63,185,80,0.4)';
    ctx.lineWidth=1;ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(hx1,pad.t);ctx.lineTo(hx1,pad.t+cH);ctx.stroke();
    ctx.beginPath();ctx.moveTo(hx2,pad.t);ctx.lineTo(hx2,pad.t+cH);ctx.stroke();
    ctx.setLineDash([]);
    // Label
    ctx.fillStyle='rgba(63,185,80,0.8)';
    ctx.font='10px monospace';
    ctx.fillText('Хедж',hx1+2,pad.t+12);
  }
  
  // Working window zone
  var fwMin=filtered[0]?filtered[0].price:0;
  var fwMax=filtered[filtered.length-1]?filtered[filtered.length-1].price:0;
  if(fwMin && fwMax){
    var fx1=toX(fwMin),fx2=toX(fwMax);
    ctx.fillStyle='rgba(88,166,255,0.06)';
    ctx.fillRect(fx1,pad.t,fx2-fx1,cH);
  }
  
  // Draw gamma curve - smooth line
  ctx.beginPath();
  ctx.strokeStyle='#f0883e';
  ctx.lineWidth=2;
  allRows.forEach(function(r,i){
    var x=toX(r.price),y=toY(r.gamma);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.stroke();
  
  // Fill under curve
  ctx.beginPath();
  allRows.forEach(function(r,i){
    var x=toX(r.price),y=toY(r.gamma);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.lineTo(toX(allRows[allRows.length-1].price),pad.t+cH);
  ctx.lineTo(toX(allRows[0].price),pad.t+cH);
  ctx.closePath();
  var grad=ctx.createLinearGradient(0,pad.t,0,pad.t+cH);
  grad.addColorStop(0,'rgba(240,136,62,0.25)');
  grad.addColorStop(1,'rgba(240,136,62,0.02)');
  ctx.fillStyle=grad;
  ctx.fill();
  
  // Draw extra profiles (individual option gammas)
  var colors=['#58a6ff','#f778ba','#7ee787','#d2a8ff','#ff7b72','#79c0ff'];
  extraProfiles.forEach(function(ep,epIdx){
    ctx.beginPath();
    ctx.strokeStyle=colors[epIdx%colors.length];
    ctx.lineWidth=1.5;
    ctx.setLineDash([4,4]);
    var sorted=ep.rows.slice().sort(function(a,b){return b.price-a.price;});
    var epMax=-1,epMaxPrice=-1;
    sorted.forEach(function(r,i){
      var x=toX(r.price),y=toY(r.gamma);
      if(r.gamma>epMax){epMax=r.gamma;epMaxPrice=r.price;}
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
    // Mark max gamma for this profile
    var mx=toX(epMaxPrice),my=toY(epMax);
    ctx.beginPath();ctx.arc(mx,my,5,0,Math.PI*2);
    ctx.fillStyle=colors[epIdx%colors.length];ctx.fill();
    ctx.beginPath();ctx.arc(mx,my,8,0,Math.PI*2);
    ctx.strokeStyle=colors[epIdx%colors.length];ctx.lineWidth=2;ctx.stroke();
  });
  
  // Draw data points
  allRows.forEach(function(r){
    var x=toX(r.price),y=toY(r.gamma);
    var isFiltered=false;
    filtered.forEach(function(f){if(f.price===r.price)isFiltered=true;});
    var isMax=r.gamma===Math.max.apply(null,gammas);
    var isInHR=r.price>=hedgeLow && r.price<=hedgeHigh;
    
    if(isMax){
      ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);
      ctx.fillStyle='#58a6ff';ctx.fill();
      ctx.beginPath();ctx.arc(x,y,8,0,Math.PI*2);
      ctx.strokeStyle='#58a6ff';ctx.lineWidth=2;ctx.stroke();
    }
    ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);
    ctx.fillStyle=isMax?'#58a6ff':'#f0883e';
    ctx.fill();
    if(isInHR){
      ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);
      ctx.strokeStyle='rgba(63,185,80,0.6)';ctx.lineWidth=1.5;ctx.stroke();
    }
  });
  
  // Strike line
  var sx=toX(strike||0);
  if(sx>pad.l && sx<pad.l+cW){
    ctx.strokeStyle='rgba(255,255,255,0.3)';ctx.lineWidth=1;ctx.setLineDash([3,3]);
    ctx.beginPath();ctx.moveTo(sx,pad.t);ctx.lineTo(sx,pad.t+cH);ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle='rgba(255,255,255,0.5)';ctx.font='10px monospace';
    ctx.fillText('K='+strike,sx+3,pad.t+12);
  }
  
  // X axis line
  ctx.strokeStyle='#30363d';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(pad.l,pad.t+cH);ctx.lineTo(pad.l+cW,pad.t+cH);ctx.stroke();
  
  // Price labels
  ctx.fillStyle='#e6edf3';ctx.font='bold 12px monospace';ctx.textAlign='center';
  allRows.forEach(function(r){
    var x=toX(r.price);
    // vertical tick
    ctx.strokeStyle='#484f58';ctx.lineWidth=1.5;
    ctx.beginPath();ctx.moveTo(x,pad.t+cH);ctx.lineTo(x,pad.t+cH+6);ctx.stroke();
    // Background box
    var text='$'+r.price;
    var tw=ctx.measureText(text).width;
    ctx.fillStyle='rgba(13,17,23,0.95)';
    ctx.fillRect(x-tw/2-3, pad.t+cH+6, tw+6, 16);
    ctx.strokeStyle='#30363d';ctx.lineWidth=1;
    ctx.strokeRect(x-tw/2-3, pad.t+cH+6, tw+6, 16);
    ctx.fillStyle='#e6edf3';
    ctx.fillText(text,x,pad.t+cH+19);
  });
  
  // Y axis labels
  ctx.textAlign='right';
  for(var i=0;i<=5;i++){
    var val=gMin+gRange*(1-i/5);
    var y=pad.t+cH*(i/5);
    ctx.fillText(val.toFixed(3),pad.l-5,y+4);
  }
  ctx.save();
  ctx.translate(12,pad.t+cH/2);
  ctx.rotate(-Math.PI/2);
  ctx.textAlign='center';
  ctx.fillText('Γ',0,0);
  ctx.restore();
  
  // Legend - below prices area
  var ly=pad.t+cH+50;
  ctx.textAlign='left';ctx.font='10px monospace';
  ctx.fillStyle='#f0883e';ctx.fillRect(pad.l,ly,10,10);
  ctx.fillStyle='#8b949e';ctx.fillText('Γ',pad.l+14,ly+9);
  if(hedgeLow){
    ctx.fillStyle='rgba(63,185,80,0.6)';ctx.fillRect(pad.l+50,ly,10,10);
    ctx.fillStyle='#8b949e';ctx.fillText('Хедж-зона',pad.l+64,ly+9);
  }
  ctx.fillStyle='#58a6ff';ctx.beginPath();ctx.arc(pad.l+150,ly+5,4,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#8b949e';ctx.fillText('Макс Γ',pad.l+158,ly+9);
  ly+=15;
}

function renderOptionGreeks(data, layer){
  var el=document.getElementById('content-'+data.symbol);
  if(!el) return;
  if(!data || !data.rows || data.rows.length===0){
    el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет данных</div>';
    return;
  }
  
  // Filter rows: 0.5 <= |delta| <= 0.85
  var filtered=[];
  data.rows.forEach(function(r){
    var absD=Math.abs(r.delta);
    if(absD >= 0.5 && absD <= 0.85){
      filtered.push(r);
    }
  });
  if(filtered.length===0){
    el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет строк в диапазоне Δ 0.5–0.85</div>';
    return;
  }
  
  // Compute working window and intersection
  var priceDelta50 = filtered[0].price;  // price at delta ~0.5
  var priceDelta85 = filtered[filtered.length-1].price;  // price at delta ~0.85
  var windowLen = Math.round(Math.abs(priceDelta50 - priceDelta85));  // length of working window (rounded)
  
  // Hedge range from API
  var hedgeRange = data.hedge_range;
  var hedgeLow = hedgeRange.low;
  var hedgeHigh = hedgeRange.high;
  var hedgeLen = Math.abs(hedgeHigh - hedgeLow);
  
  // Intersection: overlap between [priceDelta85, priceDelta50] and [hedgeLow, hedgeHigh]
  var overlapLow = Math.max(priceDelta85, hedgeLow);
  var overlapHigh = Math.min(priceDelta50, hedgeHigh);
  var overlapLen = Math.max(0, overlapHigh - overlapLow);
  
  // Coverage: intersection / hedge range length
  var coverage = hedgeLen > 0 ? overlapLen / hedgeLen : 0;
  
  // Accuracy: intersection / working window length
  var accuracy = windowLen > 0 ? overlapLen / windowLen : 0;
  
  // Sum of delta changes only for rows that fall within the intersection
  var sumDeltaDD = 0;
  for (var i = 1; i < filtered.length; i++) {
    if (filtered[i].price >= overlapLow && filtered[i].price <= overlapHigh) {
      sumDeltaDD += filtered[i-1].delta - filtered[i].delta;
    }
  }
  
  // Find max gamma
  var maxGammaIdx=-1, maxGamma=-1;
  filtered.forEach(function(r, idx){
    if(r.gamma > maxGamma) { maxGamma=r.gamma; maxGammaIdx=idx; }
  });
  
  var html='<div style="display:flex;gap:24px;align-items:flex-start">';
  html+='<div style="max-height:380px;overflow-y:auto;border:1px solid var(--border);border-radius:6px"><table style="width:540px;border-collapse:collapse;font-size:13px;font-weight:600"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:4px 6px;font-size:13px">Цена</th><th style="padding:4px 6px;text-align:right;font-size:13px">Δ</th><th style="padding:4px 6px;text-align:right;font-size:13px">Γ</th><th style="padding:4px 6px;text-align:right;font-size:13px">PnL</th><th style="padding:4px 6px;text-align:right;font-size:13px">Вн.стоимость</th><th style="padding:4px 6px;text-align:right;font-size:13px">Врем.стоимость</th></tr></thead><tbody>';
  filtered.forEach(function(r, idx){
    var pnl = r.bs_price - data.entry_premium;
    var pnlCls = pnl >= 0 ? 'color:var(--green)' : 'color:var(--red)';
    
    var rowBg = '';
    // Highlight max gamma
    if(idx===maxGammaIdx) rowBg='background:rgba(88,166,255,0.15);';
    // Highlight in hedge range
    if(r.price >= hedgeLow && r.price <= hedgeHigh) {
      rowBg += 'background:rgba(63,185,80,0.15);';
    }
    
    var intrinsic = Math.max(0, data.strike - r.price);
    var timeValue = r.bs_price - intrinsic;
    var tvCls = timeValue >= 0 ? 'color:var(--green)' : 'color:var(--red)';
    var intrinsicCls = intrinsic > 0 ? 'color:var(--green)' : 'color:var(--text-dim)';
    
    html+='<tr style="text-align:left;height:28px;'+rowBg+'">';
    html+='<td style="padding:2px 4px;font-weight:bold">$'+r.price+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(r.delta,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(r.gamma,6)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right;'+pnlCls+'">'+F(pnl,2)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right;'+intrinsicCls+'">'+F(intrinsic,2)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right;'+tvCls+'">'+F(timeValue,2)+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  html+='<div style="padding:16px 24px;background:var(--surface);border-radius:10px;border:1px solid var(--border);font-size:18px;white-space:nowrap">';
  html+='<div style="margin-bottom:4px"><span style="color:var(--text-dim);font-weight:600">Покрытие:</span> <b style="color:var(--blue)">'+(coverage*100).toFixed(0)+'%</b></div>';
  html+='<div style="margin-bottom:4px"><span style="color:var(--text-dim);font-weight:600">Точность покрытия:</span> <b style="color:var(--purple)">'+(accuracy*100).toFixed(0)+'%</b></div>';
  html+='<div><span style="color:var(--text-dim);font-weight:600">ΣΔΔ пересечение:</span> <b style="color:var(--green)">'+F(sumDeltaDD,4)+'</b></div>';
  html+='</div>';
  html+='<div style="width:620px;flex-shrink:0"><div style="font-size:14px;font-weight:bold;margin-bottom:6px;color:var(--text-dim)">Профиль Γ</div><div style="border:1px solid var(--border);border-radius:6px;padding:8px;background:var(--surface)"><canvas id="gammaChart-'+(data.symbol.replace(/[^a-zA-Z0-9]/g,'_'))+'" width="580" height="380"></canvas></div></div>';
  html+='</div>';
  
  el.innerHTML=html;
  
  // Draw gamma chart
  var chartId='gammaChart-'+data.symbol.replace(/[^a-zA-Z0-9]/g,'_');
  setTimeout(function(){
    drawGammaChart(data.rows, filtered, data.strike, hedgeLow, hedgeHigh, chartId);
    var c=document.getElementById(chartId);
    if(c) console.log('gammaChart drawn:', chartId, c.width, 'x', c.height);
  }, 50);
}








// === Global Available Options Table ===
function renderGlobalLayer(data){
  if(!data) return;
  var el=document.getElementById("globalLayerContent");
  if(!el) return;
  var opts=data.options||[];
  if(opts.length===0){el.innerHTML='<div style="padding:12px;color:var(--text-dim)">Нет опционов</div>';return;}
  var html='';
  html+='<div style="max-height:400px;overflow-y:auto;border:1px solid var(--border);border-radius:4px"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:3px 6px">Символ</th><th style="padding:3px 6px;text-align:right">Strike</th><th style="padding:3px 6px;text-align:center">DTE</th><th style="padding:3px 6px;text-align:right">Δ</th><th style="padding:3px 6px;text-align:right">IV</th><th style="padding:3px 6px;text-align:right">Θ</th><th style="padding:3px 6px;text-align:right">ν</th><th style="padding:3px 6px;text-align:right">Price</th></tr></thead><tbody>';
  opts.forEach(function(o){
    var rowCls=o.is_layer_match?'background:rgba(63,185,80,0.12);':'';
    var sym=o.symbol.replace(/'/g,"\\'");
    var purchased=globalPurchasedSymbols[o.symbol];
    if(purchased){rowCls+='background:rgba(255,200,0,0.1);';}
    html+='<tr style="text-align:left;height:24px;cursor:pointer;'+rowCls+' onclick="window.__so(\''+o.layer+'\',\''+sym+'\')" ondblclick="event.preventDefault();event.stopPropagation();window.__as(\''+o.layer+'\',\''+sym+'\')">';
    html+='<td style="padding:2px 6px;font-weight:bold">'+o.symbol+(purchased?'<span style="color:#f0ad4e"> 📌'+purchased+'</span>':'')+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+o.strike+'</td>';
    html+='<td style="padding:2px 6px;text-align:center">'+o.dte+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.delta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.iv,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.theta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(o.vega,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(o.price,4)+'</td>';
    html+='</tr>';
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
  api("/api/layer/"+layer+qs).then(function(data){renderLayer(data);});
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
  api("/api/layer/"+layer+qs).then(function(data){renderLayer(data);});
}

function refreshLayers(layer){
  var params=layerFilterParams[layer]?"?"+layerFilterParams[layer]:"";
  if(params&&!params.includes("refresh=1")) params+="&refresh=1";
  if(!params) params="?refresh=1";
  api("/api/layer/"+layer+params).then(function(data){renderLayer(data);});
}

// === Load all ===
var combinedLadder=null;
function showDataStatus(){
  // Берём data_source из ближайшего слоя
  var sources = [
    layerData_distant,
    layerData_mid,
    layerData_near
  ];
  // Also check main options endpoint
  if(window._lastOptionsData && window._lastOptionsData.data_source){
    var src = window._lastOptionsData.data_source;
    if(src !== "live") { worstSource = src; worstAge = 0; }
  }
  var worstSource = "live";
  var worstAge = -1;
  for(var i=0; i<sources.length; i++){
    var s = sources[i];
    if(!s) continue;
    var src = s.data_source || "live";
    var age = s.data_age_minutes || -1;
    // Определяем "худший" источник
    if(src === "no_data" && worstSource !== "no_data") { worstSource=src; worstAge=age; }
    else if(src === "db_fallback" && worstSource !== "no_data") { worstSource=src; worstAge=age; }
    else if(worstAge < 0 && age > 0) { worstSource=src; worstAge=age; }
  }
  var banner = document.getElementById("dataStatusBanner");
  if(!banner) return;
  if(worstSource === "no_data"){
    banner.style.display = "block";
    banner.style.background = "rgba(248,81,73,0.15)";
    banner.style.border = "1px solid var(--red)";
    banner.style.borderRadius = "6px";
    banner.style.margin = "0 24px 12px";
    banner.style.padding = "8px 16px";
    banner.style.fontSize = "13px";
    banner.style.color = "var(--red)";
    banner.innerHTML = "⛔ <b>Нет данных</b> — Bybit недоступен, снапшотов нет. Проверьте подключение.";
  } else if(worstSource === "db_fallback"){
    var ageStr = worstAge > 0 ? ("данные от " + worstAge + " мин. назад") : "данные устаревшие";
    banner.style.display = "block";
    banner.style.background = "rgba(210,153,34,0.15)";
    banner.style.border = "1px solid var(--yellow)";
    banner.style.borderRadius = "6px";
    banner.style.margin = "0 24px 12px";
    banner.style.padding = "8px 16px";
    banner.style.fontSize = "13px";
    banner.style.color = "var(--yellow)";
    banner.innerHTML = "⚠️ <b>Bybit недоступен</b> — показаны " + ageStr + ". Опционы могут не совпадать с реальностью.";
  } else {
    banner.style.display = "none";
  }
}

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
    api("/api/layer/distant"+distantQ),
    api("/api/layer/mid"+midQ),
    api("/api/layer/near"+nearQ)
  ]).then(function(results){
    combinedLadder=results[5]||{ladder:[]};
    // Store options data for status check
    window._lastOptionsData = results[1] || {};
    updateDataSourceBadge(results[1] ? results[1].data_source : null);
    renderPositions(results[0]);
    renderOptions(results[1], results[0]);
    renderRecommendations(results[2]);
    renderSummary(results[3], results[1]);
    renderLayers(results[4]);
    renderPnnLadderTable(results[0]);
    loadOptionBoard();
    layerData_distant=results[6];
    layerData_mid=results[7];
    layerData_near=results[8];
    showDataStatus();
    api("/api/purchased-options").then(function(p){
      purchasedOptions={distant:p.distant||[],mid:p.mid||[],near:p.near||[]};
      renderLayer(results[6]);
      renderLayer(results[7]);
      renderLayer(results[8]);

      // Build global purchased symbols lookup
      globalPurchasedSymbols={};
      (purchasedOptions.distant||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      (purchasedOptions.mid||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      (purchasedOptions.near||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      // Load global available options
      api("/api/available-options").then(function(d){renderGlobalLayer(d);});
    });
  });
  document.getElementById('headerUpdated').textContent='Обновлено: '+new Date().toLocaleTimeString('ru-RU');
}

loadAll();