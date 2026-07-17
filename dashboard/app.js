const API="http://localhost:8083";

// === Tabs ===
document.querySelectorAll(".tab").forEach(function(t){
  t.addEventListener("click",function(){
    document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});
    document.querySelectorAll(".tab-content").forEach(function(x){x.style.display="none"; x.classList.remove("active")});
    t.classList.add("active");
    var tabEl=document.getElementById("tab-"+t.dataset.tab);
    console.log('🔘 tab clicked:', t.dataset.tab, 'tabEl:', tabEl);
    if(tabEl){
      tabEl.classList.add("active");
      tabEl.style.display="block";
      tabEl.style.setProperty("display","block","important");
      console.log('🔘 tabEl display set to block, computed:', window.getComputedStyle(tabEl).display);
    }

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
  console.log('🔘 __closeOption: id=' + optionId + ' type=' + typeof optionId + ' symbol=' + symbol);
  var pnlStr = pnl >= 0 ? ('+' + F(pnl)) : '-' + F(Math.abs(pnl));
  if (!confirm('Закрыть ' + symbol + '\n\nPnL: ' + pnlStr + '\n\nТекущая цена будет взята из Greeks.')) return;
  fetch(API+'/api/close-option', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({option_id: optionId, close_reason: 'manual'})
  }).then(function(r){ return r.json(); }).then(function(res) {
    console.log('🔘 close-option response:', res);
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
    banner.innerHTML='⚠️ <b>Bybit недоступен</b> - показаны данные из кэша. Опционы могут не совпадать с реальностью.';
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

// === TAB 1: PORTFOLIO ===
function loadPortfolio(){
  console.log('📡 loadPortfolio called');
  fetch(API+"/api/portf")
    .then(function(r){return r.json();})
    .then(function(d){
      console.log('📡 loadPortfolio got data:', d);
      renderPortfolio(d);
    })
    .catch(function(e){console.error('📡 loadPortfolio error:', e);});
}

// === Портфель: ручной ввод текущей цены ===
window._portfManualPrices = {};

window.__editPortfPrice = function(token){
  var td = event.target;
  var val = td.textContent.replace(/[^0-9.]/g,'');
  var oldPrice = parseFloat(val) || 0;
  var manual = window._portfManualPrices[token] || oldPrice;
  td.innerHTML='<input type="number" step="0.01" min="0" value="'+F(manual,2)+'" style="width:70px;background:var(--bg);border:1px solid var(--blue);color:var(--text);padding:1px 4px;border-radius:3px;text-align:right" onblur="window.__savePortfPrice(\''+token+'\',this)" onkeydown="if(event.key===\'Enter\')this.blur();if(event.key===\'Escape\'){this.value=\''+F(oldPrice,2)+'\';this.blur()}" autofocus>';
  td.querySelector('input').focus();
  td.querySelector('input').select();
};

window.__savePortfPrice = function(token, input){
  var newPrice = parseFloat(input.value);
  if(isNaN(newPrice) || newPrice <= 0) return;
  window._portfManualPrices[token] = newPrice;
  loadPortfolio();
};

function renderPortfolio(data){
  console.log('>>> renderPortfolio', data);
  var portT=document.getElementById("portTable");
  console.log('>>> portT', portT);
  if(!portT){ console.error('portTable NOT FOUND'); return; }
  if(!data || !data.positions || data.positions.length===0){
    portT.innerHTML='<tr><td colspan="8" style="color:red">Нет данных</td></tr>';
    console.log('>>> no data');
    return;
  }
  var rows="";
  var totalInvest=0,totalCap=0,totalDiff=0;
  data.positions.forEach(function(p){
    // Используем ручную цену если задана
    var current = window._portfManualPrices[p.token] || p.current_price;
    var invest = p.avg_price * p.qty;
    var cap = current * p.qty;
    var diff = cap - invest;
    var yield_ = invest > 0 ? (diff / invest * 100) : 0;
    var yieldColor = yield_ >= 0 ? 'green' : 'red';
    var diffColor = diff >= 0 ? 'green' : 'red';
    var isManual = window._portfManualPrices.hasOwnProperty(p.token);
    var currentStyle = isManual ? 'border-bottom:1px dashed var(--blue);cursor:pointer' : 'cursor:pointer';
    var currentTitle = isManual ? '📝 Ручная цена. Клик: изменить' : 'Клик: изменить';
    rows+='<tr><td><b>'+p.token+'</b></td><td>'+F(p.qty,2)+'</td>';
    rows+='<td>$'+F(p.avg_price)+'</td><td style="'+currentStyle+'" title="'+currentTitle+'" onclick="window.__editPortfPrice(\''+p.token+'\')">$'+F(current,2)+'</td>';
    rows+='<td>$'+F(invest)+'</td><td>$'+F(cap)+'</td>';
    rows+='<td style="color:'+diffColor+'">$'+F(diff)+'</td>';
    rows+='<td style="color:'+yieldColor+'">'+P(yield_)+'</td></tr>';
    totalInvest+=invest;
    totalCap+=cap;
    totalDiff+=diff;
  });
  var diffColor=totalDiff>=0?'green':'red';
  rows+='<tr style="font-weight:bold;border-top:2px solid var(--border)"><td colspan="4">Итого</td>';
  rows+='<td>$'+F(totalInvest)+'</td><td>$'+F(totalCap)+'</td>';
  rows+='<td style="color:'+diffColor+'">$'+F(totalDiff)+'</td>';
  var totalYield=totalInvest>0?(totalDiff/totalInvest*100):0;
  rows+='<td style="color:'+diffColor+'">'+P(totalYield)+'</td></tr>';
  console.log('>>> setting innerHTML, length:', rows.length);
  portT.innerHTML=rows;
  // Force reflow for hidden tab
  void portT.offsetHeight;
  console.log('>>> DONE, innerHTML:', portT.innerHTML.substring(0,100));
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
    var layerDisplay = o.layer && LAYER_LABELS[o.layer] ? LAYER_LABELS[o.layer] : (o.layer || '-').toUpperCase();
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
  // Net Greeks - итоговая строка внизу таблицы
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
    html+='<div class="'+pnlCls+'" style="font-size:16px;font-weight:600">'+(ly.pnl!==0?((ly.pnl>=0?"+$":"-$")+F(Math.abs(ly.pnl))):'-')+'</div></div>';
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
    rl.innerHTML='<div style="color:var(--text-dim);padding:12px">Нет рекомендаций - все позиции в норме</div>';
  } else {
    var html="";
    recs.forEach(function(s){
      var ac=s.recommendation.action;
      var cls="action-"+ac.toLowerCase();
      html+='<div class="rec-item '+cls+'">'+
        '<div class="rec-meta"><b>'+s.symbol+'</b><br>'+
        'Strike $'+s.strike+' | DTE '+s.dte+' | PnL '+F(s.pnl_pct)+'%<br><br>'+
        B(ac)+' '+PB(s.recommendation.priority)+'</div>'+
        '<div class="rec-detail">'+ac+' - '+s.recommendation.reason+'</div></div>';
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
selectedOption.distant=selectedOption.distant||[];
selectedOption.mid=selectedOption.mid||[];
selectedOption.near=selectedOption.near||[];


var layerDefaults={distant:{delta_min:0.05,delta_max:0.20,dte_min:25,dte_max:99999},mid:{delta_min:0.20,delta_max:0.40,dte_min:10,dte_max:25},near:{delta_min:0.25,delta_max:0.45,dte_min:5,dte_max:25}};
var purchasedOptions={distant:[],mid:[],near:[]};
var globalPurchasedSymbols={};

window.__so = function(layer,symbol){
  selectOption(layer,symbol);
};

window.__as = function(layer,symbol){
  console.log('__as START: layer='+layer+' symbol='+symbol);
  if(!layer||!selectedOption[layer]) { console.log('__as: invalid layer='+layer); return; }
  // Double-click: add to selectedOption array
  var data;
  if(layer==='distant') data=layerData_distant;
  else if(layer==='mid') data=layerData_mid;
  else data=layerData_near;
  console.log('__as: data='+data+' data.options='+data?.options?.length);
  var found=null;
  if(data && data.options){
    for(var i=0;i<data.options.length;i++){
      if(data.options[i].symbol===symbol){found=data.options[i];break;}
    }
  }
  console.log('__as: found='+found);
  var newItem;
  if(found){
    newItem = {symbol:symbol, strike:found.strike, dte:found.dte, iv:found.iv, price:found.price, delta:found.delta, gamma:found.gamma, theta:found.theta, vega:found.vega, spot_at_entry:found.spot_price, spot_price:found.spot_price};
  } else {
    newItem = {symbol:symbol};
  }
  // Don't add duplicates
  if(selectedOption[layer].find(function(x){return x.symbol===symbol})){
    console.log('__as: already selected, refreshing aggregator');
    createAggregatorTab(layer);
    return;
  }
  selectedOption[layer].push(newItem);
  console.log('__as: selectedOption now has', selectedOption[layer].length, 'items');

  // Sync to localStorage
  var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
  if(!selList[layer]) selList[layer]=[];
  if(!selList[layer].find(function(x){return x.symbol===symbol})){
    var item=JSON.parse(JSON.stringify(newItem));
    item.qty=1;
    selList[layer].push(item);
    localStorage.setItem('selectedOptions',JSON.stringify(selList));
  }

  // Create dynamic sub-tab for this option
  if(found && layer==='near') {
    createOptionTab(layer, found);
  }
  // Always refresh aggregator
  createAggregatorTab(layer);
};

function renderLayer(data){
  try {
  console.log('>>> renderLayer START data:', data ? 'exists' : 'null');
  if(!data) { console.log('>>> no data'); return; }
  var layer=data.layer;
  var el=document.getElementById("layerContent-"+layer);
  var t=document.getElementById("layerTitle-"+layer);
  if(!el) { console.log('>>> no el for layerContent-'+layer); return; }
  console.log('>>> renderLayer: layer='+layer+' count='+data.count+' options='+data.options.length);
  // Don't overwrite static HTML headers
  // if(t) t.textContent=data.label;
  var spot=data.spot_price||0;
  // Hedging range: % drop from spot
  var hedges={near:{min:3,max:10},mid:{min:8,max:15},distant:{min:15,max:30}};
  var h=hedges[layer]||{min:5,max:20};
  var lowStrike=spot*(1-h.max/100);
  var highStrike=spot*(1-h.min/100);
  // Insurance range for highlighting
  var insLow=lowStrike, insHigh=highStrike;
  var html='<div style="margin-bottom:8px;font-size:15px;font-weight:bold">Хедж: '+h.min+'-'+h.max+'% просадка | Strike $'+F(lowStrike,1)+'-$'+F(highStrike,1)+' | Всего: <b>'+data.count+'</b></div>';
  var opts=data.options||[];
  if(opts.length===0){html+='<div style="padding:12px;color:var(--text-dim)">Нет опционов</div>';el.innerHTML=html;return;}
  // Sort by strike desc, then DTE desc
  opts.sort(function(a,b){
    if(b.strike-a.strike!==0) return b.strike-a.strike;
    return b.dte-a.dte;
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

  // For distant: store layer info on tbody for dblclick handler
  var tbodyId=(layer==='distant')?'distantLayerBody':'layerBody-'+layer;
  
  html+='<div style="max-height:250px;overflow-y:auto;border:1px solid var(--border);border-radius:4px"><table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:2px 4px">Символ</th><th style="padding:2px 4px;text-align:center">Drop%</th><th style="padding:2px 4px;text-align:right">Strike</th><th style="padding:2px 4px;text-align:center">DTE</th><th style="padding:2px 4px;text-align:right">Premium</th><th style="padding:2px 4px;text-align:right">Δ</th><th style="padding:2px 4px;text-align:right">Γ</th><th style="padding:2px 4px;text-align:right">Θ</th><th style="padding:2px 4px;text-align:right">IV</th><th style="padding:2px 4px;text-align:right">OI</th><th style="padding:2px 4px;text-align:right">Volume</th><th style="padding:2px 4px;text-align:right">Spread</th></tr></thead><tbody id="'+tbodyId+'">';
  opts.forEach(function(o){
    var sym=o.symbol.replace(/'/g,"\\'");
    var dropPct=spot>0?((spot-o.strike)/spot*100):0;
    var dropCls=dropPct>=0?'color:var(--green)':'color:#d32f2f';
    var dropStr=(dropPct>=0?'+':'')+F(dropPct,2)+'%';
    var title='Один клик: выделить, двойной: добавить | IV ATM: '+F(o.iv_atm,4);
    var purchased=purchSymbols[o.symbol];
    if(purchased) title+=' | 📌 Куплено: '+purchased;
    // Highlight insurance range strikes in green
    var rowBg='';
    if(o.strike>=insLow && o.strike<=insHigh){rowBg='background:rgba(63,185,80,0.12);';}
    if(layer==='distant'){
      html+='<tr style="text-align:left;height:22px;cursor:pointer;'+rowBg+' data-symbol="'+o.symbol+'" ondblclick="event.preventDefault();event.stopPropagation();addDistant(\''+o.symbol.replace(/'/g,"\\'")+'\')" title="'+title+'">';
    } else {
      html+='<tr style="text-align:left;height:22px;cursor:pointer;'+rowBg+' onclick="window.__so(\''+layer+'\',\''+o.symbol.replace(/'/g,"\\'")+'\')" ondblclick="event.preventDefault();event.stopPropagation();window.__as(\''+layer+'\',\''+o.symbol.replace(/'/g,"\\'")+'\')" title="'+title+'">';
    }
    html+='<td style="padding:2px 4px;font-weight:bold">'+o.symbol+(purchased?'<span style="color:#f0ad4e">📌'+purchased+'</span>':'')+'</td>';
    html+='<td style="padding:2px 4px;text-align:center;color:'+dropCls+'"><b>'+dropStr+'</b></td>';
    var strikeCell='';
    if(o.strike>=insLow && o.strike<=insHigh){strikeCell='<b style="color:var(--green)" title="Диапазон страхования">🛡️ $'+o.strike+'</b>';}else if(closest2.indexOf(o.strike)!==-1){strikeCell='<b style="color:var(--blue)" title="Ближайший к spot">🎯 $'+o.strike+'</b>';}else{strikeCell='$'+o.strike;}
    html+='<td style="padding:2px 4px;text-align:right">'+strikeCell+'</td>';
    html+='<td style="padding:2px 4px;text-align:center">'+o.dte+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">$'+F(o.price,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(o.delta,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(o.gamma,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(o.theta,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+F(o.iv,4)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+(o.open_interest||0)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+(o.volume||o.open_interest||0)+'</td>';
    html+='<td style="padding:2px 4px;text-align:right">'+(o.spread||'-')+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  el.innerHTML=html;
  
  // Save data for __as lookup
  if(layer==='near') window.layerData_near=data;
  else if(layer==='mid') window.layerData_mid=data;
  else if(layer==='distant') { window.layerData_distant=data; console.log('>>> renderLayer: set layerData_distant, options='+data.options.length); }
  console.log('>>> renderLayer DONE');
  } catch(e){ console.error('>>> renderLayer ERROR:', e); }
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

window._dbClick=function(layer,symbol){
  if(!layer||!symbol||layer==='undefined') return;
  if(layer==='distant'){ addDistant(symbol); }
  else { window.__as(layer,symbol); }
};

// === Distant: add selected option ===
function addDistant(symbol){
  console.log('addDistant called: symbol='+symbol);
  for(var i=0;i<selectedOption.distant.length;i++){
    if(selectedOption.distant[i].symbol===symbol) { console.log('addDistant: already selected'); return; }
  }
  var data=window.layerData_distant;
  if(!data||!data.options) { console.log('addDistant: no data'); return; }
  var found=null;
  for(var i=0;i<data.options.length;i++){
    if(data.options[i].symbol===symbol){found=data.options[i];break;}
  }
  if(!found) return;
  var item={symbol:found.symbol,strike:found.strike,dte:found.dte,iv:found.iv,price:found.price,delta:found.delta,gamma:found.gamma,theta:found.theta,vega:found.vega,spot_at_entry:found.spot_price,qty:1,checked:true};
  selectedOption.distant.push(item);
  var selList=JSON.parse(localStorage.getItem('selectedDistant')||'[]');
  if(!selList.find(function(x){return x.symbol===symbol})){
    selList.push(JSON.parse(JSON.stringify(item)));
    localStorage.setItem('selectedDistant',JSON.stringify(selList));
  }
  syncDistantSelected();
  renderDistantGammaChart();
  renderDistantDeltaMatrix();
  renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
}

// === Distant: render selected table ===
function syncDistantSelected(){
  var tbody=document.getElementById('distantSelectedTable');
  if(!tbody) return;
  var opts=selectedOption.distant||[];
  var html='';
  var sumTotal=0;
  opts.forEach(function(opt,idx){
    var checked=opt.checked!==false;
    var strike=opt.strike||'-';
    var delta=opt.delta||0;
    var price=opt.price||0;
    var qty=opt.qty||1;
    var total=price*qty;
    if(checked) sumTotal+=total;
    html+='<tr style="height:22px">';
    html+='<td style="padding:2px 6px;text-align:center"><input type="checkbox" '+(checked?'checked':'')+' onchange="window._onDistantToggle('+idx+',this.checked)"></td>';
    html+='<td style="padding:2px 6px;font-weight:bold">'+opt.symbol+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+strike+'</td>';
    html+='<td style="padding:2px 6px;text-align:center">'+(opt.dte||'-')+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(delta,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(price,4)+'</td>';
    html+='<td style="padding:2px 6px;text-align:center"><input type="number" min="0" step="1" value="'+qty+'" style="width:50px;text-align:center;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:2px 4px;border-radius:4px" onchange="window._onDistantQtyChange('+idx+',this.value)"></td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(total,2)+'</td>';
    html+='<td style="padding:2px 6px;text-align:center"><button style="background:none;border:none;cursor:pointer;color:#d32f2f;font-size:14px" onclick="window._onDistantRemove('+idx+')">✕</button></td>';
    html+='</tr>';
  });
  if(html===''){
    html='<tr><td colspan="9" style="padding:12px;text-align:center;color:var(--text-dim)">Нет выбранных опционов</td></tr>';
  } else {
    html+='<tr style="height:22px;font-weight:bold;background:var(--bg);border-top:2px solid var(--border)">';
    html+='<td style="padding:2px 6px;text-align:center"></td>';
    html+='<td style="padding:2px 6px" colspan="4">Итого:</td>';
    html+='<td></td>';
    html+='<td style="padding:2px 6px;text-align:right">$'+F(sumTotal,2)+'</td>';
    html+='<td></td>';
    html+='</tr>';
  }
  tbody.innerHTML=html;
  renderDistantGammaChart();
  renderDistantDeltaMatrix();
  renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
}

window._onDistantToggle=function(idx,val){
  if(selectedOption.distant[idx]){
    selectedOption.distant[idx].checked=val;
    var selList=JSON.parse(localStorage.getItem('selectedDistant')||'[]');
    if(selList[idx]) selList[idx].checked=val;
    localStorage.setItem('selectedDistant',JSON.stringify(selList));
    syncDistantSelected();
    renderDistantGammaChart();
    renderDistantDeltaMatrix();
    renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
  }
};

window._onDistantQtyChange=function(idx,val){
  if(selectedOption.distant[idx]){
    selectedOption.distant[idx].qty=parseInt(val)||0;
    var selList=JSON.parse(localStorage.getItem('selectedDistant')||'[]');
    if(selList[idx]) selList[idx].qty=selectedOption.distant[idx].qty;
    localStorage.setItem('selectedDistant',JSON.stringify(selList));
    syncDistantSelected();
    renderDistantGammaChart();
    renderDistantDeltaMatrix();
    renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
  }
};

window._onDistantRemove=function(idx){
  selectedOption.distant.splice(idx,1);
  var selList=JSON.parse(localStorage.getItem('selectedDistant')||'[]');
  selList.splice(idx,1);
  localStorage.setItem('selectedDistant',JSON.stringify(selList));
  syncDistantSelected();
  renderDistantGammaChart();
  renderDistantDeltaMatrix();
  renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
};

// === BS Put Price (r=0) ===
function _bsPutPrice(S, K, T, iv){
  if(T<=0||iv<=0||S<=0||K<=0) return Math.max(K-S, 0);
  var d1=(Math.log(S/K)+(iv*iv/2)*T)/(iv*Math.sqrt(T));
  var a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p0=0.3275911;
  var sign=d1<0?-1:1;
  var ax=Math.abs(d1)/Math.sqrt(2);
  var t=1/(1+p0*ax);
  var poly=((( (a5*t+a4)*t+a3 )*t+a2)*t+a1)*t;
  var y=poly*Math.exp(-ax*ax);
  var Nd1=0.5*(1+sign*(1-y));
  var d2=d1-iv*Math.sqrt(T);
  sign=d2<0?-1:1;
  ax=Math.abs(d2)/Math.sqrt(2);
  t=1/(1+p0*ax);
  poly=((( (a5*t+a4)*t+a3 )*t+a2)*t+a1)*t;
  y=poly*Math.exp(-ax*ax);
  var Nd2=0.5*(1+sign*(1-y));
  return K*(1-Nd2)-S*(1-Nd1);
}

// === Distant: PnL Matrix ===
function renderDistantPnlMatrix(){
  var tbody=document.querySelector('#distantPnlMatrix tbody');
  var thead=document.querySelector('#distantPnlMatrix thead tr');
  if(!tbody||!thead) return;
  var allOpts=selectedOption.distant||[];
  var opts=allOpts.filter(function(o){return o.checked!==false;});
  if(opts.length===0){tbody.innerHTML='<tr><td colspan="2" style="padding:12px;text-align:center;color:var(--text-dim)">Нет выбранных опционов</td></tr>';thead.innerHTML='<tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0"><th style="text-align:right;padding:2px 6px">Цена</th><th style="text-align:right;padding:2px 6px">%Просадка</th></tr>';return;}
  var data=window.layerData_distant;
  if(!data||!data.spot_price) return;
  var spot=data.spot_price;
  var insLow=Math.round(spot*0.70);
  var insHigh=Math.round(spot*0.85);
  var dropPct20=Math.round(spot*0.80);
  var dropPct25=Math.round(spot*0.75);
  thead.innerHTML='';
  var thPrice=document.createElement('th');
  thPrice.style.cssText='text-align:right;padding:2px 6px';
  thPrice.textContent='Цена';
  thead.appendChild(thPrice);
  var thDrop=document.createElement('th');
  thDrop.style.cssText='text-align:right;padding:2px 6px';
  thDrop.textContent='%Просадка';
  thead.appendChild(thDrop);
  opts.forEach(function(o){
    var th=document.createElement('th');
    th.style.cssText='text-align:right;padding:2px 6px';
    th.textContent=o.symbol.replace('-P','');
    thead.appendChild(th);
  });
  var html='';
  for(var p=insHigh;p>=insLow;p--){
    var is20=(p===dropPct20);
    var is25=(p===dropPct25);
    var bg=is25?'background:#ff000030':(is20?'background:#ffaa0020':'');
    html+='<tr style="height:20px;'+bg+'">';
    html+='<td style="padding:2px 6px;text-align:right">$'+p+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F((spot-p)/spot*100,1)+'%</td>';
    opts.forEach(function(o){
      var qty=o.qty||1;
      var strike=o.strike||0;
      var premium=o.price||0;
      var iv=o.iv||0.3;
      var dte=Math.max(o.dte||30,1);
      var T=dte/365;
      var bsPrice=_bsPutPrice(p, strike, T, iv);
      var pnl=(bsPrice-premium)*qty;
      var cls=pnl>=0?'color:var(--green)':'color:#d32f2f';
      html+='<td style="padding:2px 6px;text-align:right" class="'+cls+'">$'+F(pnl,2)+'</td>';
    });
    html+='</tr>';
  }
  // PnL difference row (last - first)
  html+='<tr style="height:20px;font-weight:bold;background:var(--bg);border-top:2px solid var(--border)">';
  html+='<td style="padding:2px 6px;text-align:right" colspan="2">Разница PnL:</td>';
  opts.forEach(function(o){
    var qty=o.qty||1;
    var strike=o.strike||0;
    var premium=o.price||0;
    var iv=o.iv||0.3;
    var dte=Math.max(o.dte||30,1);
    var T=dte/365;
    var pnlFirst=(_bsPutPrice(insHigh, strike, T, iv)-premium)*qty;
    var pnlLast=(_bsPutPrice(insLow, strike, T, iv)-premium)*qty;
    var diff=pnlLast-pnlFirst;
    var cls=diff>=0?'color:var(--green)':'color:#d32f2f';
    html+='<td style="padding:2px 6px;text-align:right" class="'+cls+'">$'+F(diff,2)+'</td>';
  });
  html+='</tr>';
  tbody.innerHTML=html;
}

// === Distant: Delta Matrix ===
function renderDistantDeltaMatrix(){
  var tbody=document.querySelector('#distantDeltaMatrix tbody');
  var thead=document.querySelector('#distantDeltaMatrix thead tr');
  if(!tbody||!thead) return;
  var allOpts=selectedOption.distant||[];
  var opts=allOpts.filter(function(o){return o.checked!==false;});
  if(opts.length===0){tbody.innerHTML='<tr><td colspan="2" style="padding:12px;text-align:center;color:var(--text-dim)">Нет выбранных опционов</td></tr>';thead.innerHTML='<tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0"><th style="text-align:right;padding:2px 6px">Цена</th><th style="text-align:right;padding:2px 6px">%Просадка</th></tr>';return;}
  var data=window.layerData_distant;
  if(!data||!data.spot_price) return;
  var spot=data.spot_price;
  var insLow=Math.round(spot*0.70);
  var insHigh=Math.round(spot*0.85);
  var dropPct20=Math.round(spot*0.80);
  var dropPct25=Math.round(spot*0.75);
  thead.innerHTML='';
  var thPrice=document.createElement('th');
  thPrice.style.cssText='text-align:right;padding:2px 6px';
  thPrice.textContent='Цена';
  thead.appendChild(thPrice);
  var thDrop=document.createElement('th');
  thDrop.style.cssText='text-align:right;padding:2px 6px';
  thDrop.textContent='%Просадка';
  thead.appendChild(thDrop);
  opts.forEach(function(o){
    var th=document.createElement('th');
    th.style.cssText='text-align:right;padding:2px 6px';
    th.textContent=o.symbol.replace('-P','');
    thead.appendChild(th);
  });
  var html='';
  for(var p=insHigh;p>=insLow;p--){
    var is20=(p===dropPct20);
    var is25=(p===dropPct25);
    var bg=is25?'background:#ff000030':(is20?'background:#ffaa0020':'');
    html+='<tr style="height:20px;'+bg+'">';
    html+='<td style="padding:2px 6px;text-align:right">$'+p+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F((spot-p)/spot*100,1)+'%</td>';
    opts.forEach(function(o){
      var qty=o.qty||1;
      var strike=o.strike||0;
      var iv=o.iv||0.3;
      var dte=Math.max(o.dte||30,1);
      var T=dte/365;
      var d1=(Math.log(p/strike)+(iv*iv/2)*T)/(iv*Math.sqrt(T));
      var a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p0=0.3275911;
      var sign=d1<0?-1:1;
      var ax=Math.abs(d1)/Math.sqrt(2);
      var t=1/(1+p0*ax);
      var poly=((( (a5*t+a4)*t+a3 )*t+a2)*t+a1)*t;
      var y=poly*Math.exp(-ax*ax);
      var cdf=0.5*(1+sign*(1-y));
      var delta=cdf-1;
      html+='<td style="padding:2px 6px;text-align:right">'+F(delta*qty,2)+'</td>';
    });
    html+='</tr>';
  }
  // Delta difference row (last - first)
  html+='<tr style="height:20px;font-weight:bold;background:var(--bg);border-top:2px solid var(--border)">';
  html+='<td style="padding:2px 6px;text-align:right" colspan="2">Разница Δ:</td>';
  opts.forEach(function(o){
    var qty=o.qty||1;
    var strike=o.strike||0;
    var iv=o.iv||0.3;
    var dte=Math.max(o.dte||30,1);
    var T=dte/365;
    var deltaFirst=(function(){var d1=(Math.log(insHigh/strike)+(iv*iv/2)*T)/(iv*Math.sqrt(T));var s=d1<0?-1:1;var a=Math.abs(d1)/Math.sqrt(2);var t=1/(1+0.3275911*a);var p=((( (1.061405429*t+-1.453152027)*t+1.421413741 )*t+-0.284496736)*t+0.254829592)*t;var y=p*Math.exp(-a*a);return 0.5*(1+s*(1-y))-1;})();
    var deltaLast=(function(){var d1=(Math.log(insLow/strike)+(iv*iv/2)*T)/(iv*Math.sqrt(T));var s=d1<0?-1:1;var a=Math.abs(d1)/Math.sqrt(2);var t=1/(1+0.3275911*a);var p=((( (1.061405429*t+-1.453152027)*t+1.421413741 )*t+-0.284496736)*t+0.254829592)*t;var y=p*Math.exp(-a*a);return 0.5*(1+s*(1-y))-1;})();
    var diff=(deltaLast-deltaFirst)*qty;
    var cls=diff<0?'color:var(--green)':'color:#d32f2f';
    html+='<td style="padding:2px 6px;text-align:right" class="'+cls+'">'+F(diff,2)+'</td>';
  });
  html+='</tr>';
  tbody.innerHTML=html;
}

// === Distant: Summary Matrix ===
function renderDistantSummaryMatrix(){
  var tbody=document.querySelector('#distantSummaryMatrix tbody');
  var thead=document.querySelector('#distantSummaryMatrix thead tr');
  if(!tbody||!thead) return;
  var allOpts=selectedOption.distant||[];
  var opts=allOpts.filter(function(o){return o.checked!==false;});
  if(opts.length===0){tbody.innerHTML='<tr><td colspan="5" style="padding:12px;text-align:center;color:var(--text-dim)">Нет выбранных опционов</td></tr>';return;}
  var data=window.layerData_distant;
  if(!data||!data.spot_price) return;
  var spot=data.spot_price;
  var insLow=Math.round(spot*0.70);
  var insHigh=Math.round(spot*0.85);
  var dropPct20=Math.round(spot*0.80);
  var dropPct25=Math.round(spot*0.75);
  var html='';
  for(var p=insHigh;p>=insLow;p--){
    var is20=(p===dropPct20);
    var is25=(p===dropPct25);
    var bg=is25?'background:#ff000030':(is20?'background:#ffaa0020':'');
    var totalPnl=0;
    var totalDelta=0;
    var totalGamma=0;
    opts.forEach(function(o){
      var qty=o.qty||1;
      var strike=o.strike||0;
      var premium=o.price||0;
      var iv=o.iv||0.3;
      var dte=Math.max(o.dte||30,1);
      var T=dte/365;
      var bsPrice=_bsPutPrice(p, strike, T, iv);
      var pnl=(bsPrice-premium)*qty;
      totalPnl+=pnl;
      var d1=(Math.log(p/strike)+(iv*iv/2)*T)/(iv*Math.sqrt(T));
      var a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p0=0.3275911;
      var sign=d1<0?-1:1;
      var ax=Math.abs(d1)/Math.sqrt(2);
      var t=1/(1+p0*ax);
      var poly=((( (a5*t+a4)*t+a3 )*t+a2)*t+a1)*t;
      var y=poly*Math.exp(-ax*ax);
      var cdf=0.5*(1+sign*(1-y));
      var delta=cdf-1;
      totalDelta+=delta*qty;
      var npdf=Math.exp(-d1*d1/2)/Math.sqrt(2*Math.PI);
      var gamma=npdf/(p*iv*Math.sqrt(T));
      totalGamma+=gamma*qty;
    });
    html+='<tr style="height:20px;'+bg+'">';
    html+='<td style="padding:2px 6px;text-align:right">$'+p+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F((spot-p)/spot*100,1)+'%</td>';
    var pnlCls=totalPnl>=0?'color:var(--green)':'color:#d32f2f';
    html+='<td style="padding:2px 6px;text-align:right" class="'+pnlCls+'">$'+F(totalPnl,2)+'</td>';
    var deltaCls=totalDelta>=0?'color:var(--green)':'color:#d32f2f';
    html+='<td style="padding:2px 6px;text-align:right" class="'+deltaCls+'">'+F(totalDelta,2)+'</td>';
    html+='<td style="padding:2px 6px;text-align:right">'+F(totalGamma,4)+'</td>';
    html+='</tr>';
  }
  tbody.innerHTML=html;
}

// === Distant: Gamma Profile Chart ===
function renderDistantGammaChart(){
  var container=document.getElementById('distantGammaChart');
  if(!container) return;
  var allOpts=selectedOption.distant||[];
  var opts=allOpts.filter(function(o){return o.checked!==false && (o.qty||0)>0;});
  if(opts.length===0){container.innerHTML='Нет выбранных опционов';return;}
  
  var data=window.layerData_distant;
  if(!data||!data.spot_price){container.innerHTML='Нет данных';return;}
  var spot=data.spot_price;
  
  // Insurance range: 15-30% drop
  var insLow=Math.round(spot*0.70);
  var insHigh=Math.round(spot*0.85);
  
  // X-axis: from 70% to 110% of spot
  var xMin=Math.round(spot*0.60);
  var xMax=Math.round(spot*1.10);
  var maxGamma=0;
  
  // Collect all gamma points
  var allPoints=[];
  opts.forEach(function(opt){
    var strike=opt.strike||0;
    var iv=opt.iv||0.3;
    var dte=opt.dte||30;
    var qty=opt.qty||1;
    var T=Math.max(dte/365, 1/365);
    
    function _ncdf(x){
      var a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p=0.3275911;
      var sign=x<0?-1:1;
      var ax=Math.abs(x)/Math.sqrt(2);
      var t=1/(1+p*ax);
      var poly=((( (a5*t+a4)*t+a3 )*t+a2)*t+a1)*t;
      var y=poly*Math.exp(-ax*ax);
      return 0.5*(1+sign*(1-y));
    }
    function _npdf(x){ return Math.exp(-0.5*x*x)/Math.sqrt(2*Math.PI); }
    
    var points=[];
    for(var p=xMin;p<=xMax;p+=1){
      if(T<=0||iv<=0||p<=0||strike<=0){
        points.push({price:p, gamma:0});
        continue;
      }
      var d1=(Math.log(p/strike)+(iv*iv/2)*T)/(iv*Math.sqrt(T));
      var gamma=_npdf(d1)/(p*iv*Math.sqrt(T));
      points.push({price:p, gamma:gamma*qty});
      if(gamma*qty>maxGamma) maxGamma=gamma*qty;
    }
    // Sum gamma in insurance range
    var sumGamma=0;
    for(var i=0;i<points.length;i++){
      if(points[i].price>=insLow && points[i].price<=insHigh){
        sumGamma+=points[i].gamma;
      }
    }
    var premium=opt.price||0;
    var gammaEff=premium>0?sumGamma/premium:0;
    allPoints.push({symbol:opt.symbol, points:points, strike:strike, sumGamma:sumGamma, gammaEff:gammaEff, color:null});
  });
  
  // Colors
  var colors=['#3b82f6','#ef4444','#22c55e','#f59e0b','#8b5cf6','#ec4899'];
  allPoints.forEach(function(s,i){ s.color=colors[i%colors.length]; });
  
  // Add padding to gamma
  maxGamma=maxGamma*1.1+0.001;
  
  var w=container.clientWidth||450;
  var h=container.clientHeight||280;
  var pad={l:60, r:20, t:30, b:40};
  var cw=w-pad.l-pad.r;
  var ch=h-pad.t-pad.b;
  
  var svgW=w, svgH=h;
  var svg='<svg width="'+svgW+'" height="'+svgH+'" xmlns="http://www.w3.org/2000/svg">';
  
  // Background
  svg+='<rect x="0" y="0" width="'+svgW+'" height="'+svgH+'" fill="var(--surface)"/>';
  
  var xRange=xMax-xMin;
  var yRange=maxGamma;
  
  function xPos(p){ return pad.l+(p-xMin)/xRange*cw; }
  function yPos(v){ return pad.t+(1-v/yRange)*ch; }
  
  // Green insurance zone
  var xLeft=xPos(insLow);
  var xRight=xPos(insHigh);
  var zoneW=xRight-xLeft;
  svg+='<rect x="'+xLeft+'" y="'+pad.t+'" width="'+zoneW+'" height="'+ch+'" fill="rgba(34,197,94,0.15)"/>';
  svg+='<text x="'+(xLeft+zoneW/2)+'" y="'+(pad.t+14)+'" text-anchor="middle" fill="#22c55e" font-size="10">Зона страховки ('+insLow+'-'+insHigh+')</text>';
  
  // Grid
  svg+='<line x1="'+pad.l+'" y1="'+(pad.t+ch)+'" x2="'+(pad.l+cw)+'" y2="'+(pad.t+ch)+'" stroke="#555" stroke-width="1"/>';
  svg+='<line x1="'+pad.l+'" y1="'+pad.t+'" x2="'+pad.l+'" y2="'+(pad.t+ch)+'" stroke="#555" stroke-width="1"/>';
  
  // Y-axis labels
  var yStep=0.01; if(maxGamma>0.1) yStep=0.02; if(maxGamma>0.2) yStep=0.05;
  for(var vy=0;vy<=maxGamma;vy+=yStep){
    var yy=yPos(vy);
    svg+='<text x="'+(pad.l-5)+'" y="'+(yy+4)+'" text-anchor="end" fill="#888" font-size="10">'+vy.toFixed(4)+'</text>';
  }
  
  // X-axis labels
  var xStep=5; if(xRange>100) xStep=10; if(xRange>200) xStep=25;
  for(var vx=xMin;vx<=xMax;vx+=xStep){
    var xx=xPos(vx);
    svg+='<text x="'+xx+'" y="'+(pad.t+ch+15)+'" text-anchor="middle" fill="#888" font-size="10">$'+vx+'</text>';
  }
  
  // Axis labels
  svg+='<text x="'+(pad.l+cw/2)+'" y="'+(h-5)+'" text-anchor="middle" fill="#aaa" font-size="11">Цена SOL</text>';
  svg+='<text x="12" y="'+(pad.t+ch/2)+'" text-anchor="middle" fill="#aaa" font-size="11" transform="rotate(-90,12,'+(pad.t+ch/2)+')">Гамма</text>';
  
  // Draw gamma curves
  allPoints.forEach(function(series){
    var path='';
    series.points.forEach(function(pt,pi){
      var x=xPos(pt.price);
      var y=yPos(pt.gamma);
      if(pi===0) path+='M'+x+','+y+' '; else path+='L'+x+','+y+' ';
    });
    svg+='<path d="'+path+'" fill="none" stroke="'+series.color+'" stroke-width="2"/>';
    // Strike marker
    var strikeX=xPos(series.strike);
    svg+='<line x1="'+strikeX+'" y1="'+pad.t+'" x2="'+strikeX+'" y2="'+(pad.t+ch)+'" stroke="'+series.color+'" stroke-width="1" stroke-dasharray="4,4"/>';
  });
  
  // Spot marker
  var spotX=xPos(spot);
  svg+='<line x1="'+spotX+'" y1="'+pad.t+'" x2="'+spotX+'" y2="'+(pad.t+ch)+'" stroke="#fff" stroke-width="1" stroke-dasharray="2,2"/>';
  svg+='<text x="'+spotX+'" y="'+(pad.t-5)+'" text-anchor="middle" fill="#fff" font-size="9">spot $'+spot+'</text>';
  
  // Legend
  allPoints.forEach(function(s,i){
    var ly=pad.t+15+i*14;
    svg+='<text x="'+(pad.l+cw-5)+'" y="'+ly+'" text-anchor="end" fill="'+s.color+'" font-size="10">'+s.symbol+' Γ='+F(s.sumGamma,4)+' Eff='+F(s.gammaEff,4)+'</text>';
  });
  
  svg+='</svg>';
  container.innerHTML=svg;
}

function addSelected(layer,symbol){
  // Sync selectedOption to localStorage
  var selArr=selectedOption[layer]||[];
  if(!selArr.length) return; // nothing to sync
  var selList=JSON.parse(localStorage.getItem('selectedOptions')||'{}');
  if(!selList[layer]) selList[layer]=[];
  // Remove existing symbol from localStorage
  selList[layer]=selList[layer].filter(function(x){return x.symbol!==symbol});
  // Add all items from selectedOption
  selArr.forEach(function(s){
    if(!selList[layer].find(function(x){return x.symbol===s.symbol})){
      var item=JSON.parse(JSON.stringify(s));
      if(!item.qty) item.qty=1;
      selList[layer].push(item);
    }
  });
  localStorage.setItem('selectedOptions',JSON.stringify(selList));
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

  // Re-render aggregator (always visible at bottom)
  if(foundLayer){
    var aggContent=document.getElementById('aggregatorContent');
    if(aggContent) renderAggregatorGreeks(foundLayer);
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

function initAggregator(){
  // Содержимое уже в HTML в .card, просто показываем дефолтное сообщение
  var content=document.getElementById('aggregatorContent');
  if(content) content.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">📊 <b>Суммарный</b> - выберите опционы двойным кликом</div>';
}

function createAggregatorTab(layer){
  // Просто обновляем данные
  renderAggregatorGreeks(layer);
}

function removeAggregatorTab(){
  // Суммарный теперь постоянный, не удаляем
}

function renderAggregatorGreeks(layer){
  layer=layer||'near';
  var sel=selectedOption[layer]||[];
  console.log('>>> renderAggregatorGreeks: sel.length='+sel.length);
  if(sel.length===0){
    var el=document.getElementById('aggregatorContent');
    if(el) el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет выбранных опционов</div>';
    return;
  }

  var el=document.getElementById('aggregatorContent');
  el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Загрузка...</div>';

  // Fetch BS for each selected option
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
      if(!d||!d.hedge_range||!d.hedge_range.low) return;
      allStrikes.push(d.strike);
      allHedgeRanges.push(d.hedge_range);
    });
    var avgHedgeLow=0,avgHedgeHigh=0;
    if(allHedgeRanges.length>0){
      allHedgeRanges.forEach(function(hr){avgHedgeLow+=hr.low;avgHedgeHigh+=hr.high;});
      avgHedgeLow=Math.round(avgHedgeLow/allHedgeRanges.length);
      avgHedgeHigh=Math.round(avgHedgeHigh/allHedgeRanges.length);
    }
    validResults.forEach(function(d){
      if(!d||!d.rows) return;
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
    if(displayRows.length===0) displayRows=aggregated;

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

    // Compute insurance range from layer
    var aggLayer=sel.length>0?sel[0].layer||layer:null;
    var avgSpot=0;
    if(aggLayer){
      sel.forEach(function(s){avgSpot+=s.spot_price||s.spot_at_entry||0;});
      avgSpot=Math.round(avgSpot/sel.length);
      var hedges={near:{min:3,max:10},mid:{min:8,max:15},distant:{min:15,max:30}};
      var h=hedges[aggLayer]||{min:5,max:20};
      var avgInsLow=Math.round(avgSpot*(1-h.max/100));
      var avgInsHigh=Math.round(avgSpot*(1-h.min/100));
    }
    // Fallback if not computed
    if(typeof avgInsLow==='undefined'){avgInsLow=avgHedgeLow; avgInsHigh=avgHedgeHigh;}

    // Build price-based table (like individual tabs)
    var html='';
    html+='<div style="display:flex;gap:24px;align-items:flex-start">';
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
      console.log('>>> drawGammaChart: displayRows='+displayRows.length+' validResults='+validResults.length);
      drawGammaChart(displayRows, displayRows, avgStrike, avgHedgeLow, avgHedgeHigh, 'gammaChart-aggregator', validResults, avgInsLow, avgInsHigh);
    }, 50);
  });
}

function drawGammaChart(allRows, filtered, strike, hedgeLow, hedgeHigh, chartId, extraProfiles, insLow, insHigh){
  extraProfiles = extraProfiles && Array.isArray(extraProfiles) ? extraProfiles : [];
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

  // X-axis: gamma working range [hedgeLow, hedgeHigh] ±5%
  if(!hedgeLow || !hedgeHigh || hedgeLow===hedgeHigh){
    // Fallback: use all rows price range
    var allPrices=allRows.map(function(r){return r.price;});
    xMin=Math.min.apply(null,allPrices);
    xMax=Math.max.apply(null,allPrices);
  } else {
    var margin=(hedgeHigh-hedgeLow)*0.05;
    xMin=hedgeLow-margin; xMax=hedgeHigh+margin;
  }
  var xRange=xMax-xMin;
  if(xRange===0) xRange=1; // guard
  var chartRows=allRows.filter(function(r){return r.price>=xMin && r.price<=xMax;});
  if(chartRows.length===0){
    // Fallback: use ALL rows price range
    console.log('drawGammaChart: chartRows empty, using full range');
    var allPrices=allRows.map(function(r){return r.price;});
    xMin=Math.min.apply(null,allPrices);
    xMax=Math.max.apply(null,allPrices);
    xRange=xMax-xMin||1;
    chartRows=allRows;
  }

  // Gamma range from working range data only
  var gammas=chartRows.map(function(r){return r.gamma;});
  var gMax=Math.max.apply(null,gammas)*1.1;
  var gMin=0;
  var gRange=gMax-gMin;
  if(gRange===0) gRange=1; // guard

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

  // Working window zone
  var fwMin=filtered[0]?filtered[0].price:0;
  var fwMax=filtered[filtered.length-1]?filtered[filtered.length-1].price:0;
  if(fwMin && fwMax){
    var fx1=toX(fwMin),fx2=toX(fwMax);
    ctx.fillStyle='rgba(88,166,255,0.06)';
    ctx.fillRect(fx1,pad.t,fx2-fx1,cH);
  }

  // Draw gamma curve - smooth line (using chart rows only)
  ctx.beginPath();
  ctx.strokeStyle='#f0883e';
  ctx.lineWidth=2;
  chartRows.forEach(function(r,i){
    var x=toX(r.price),y=toY(r.gamma);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.stroke();

  // Fill under curve
  ctx.beginPath();
  chartRows.forEach(function(r,i){
    var x=toX(r.price),y=toY(r.gamma);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.lineTo(toX(chartRows[chartRows.length-1].price),pad.t+cH);
  ctx.lineTo(toX(chartRows[0].price),pad.t+cH);
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
    // Filter to working range
    sorted=sorted.filter(function(r){return r.price>=xMin && r.price<=xMax;});
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

  // Draw data points (from working range only)
  chartRows.forEach(function(r){
    var x=toX(r.price),y=toY(r.gamma);
    var isMax=r.gamma===Math.max.apply(null,gammas);

    if(isMax){
      ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);
      ctx.fillStyle='#58a6ff';ctx.fill();
      ctx.beginPath();ctx.arc(x,y,8,0,Math.PI*2);
      ctx.strokeStyle='#58a6ff';ctx.lineWidth=2;ctx.stroke();
    }
    ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);
    ctx.fillStyle=isMax?'#58a6ff':'#f0883e';
    ctx.fill();
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

  // Insurance range zone (green highlight) - ONLY intersection with hedge range
  if(insLow && insHigh){
    var covLow = Math.max(hedgeLow, insLow);
    var covHigh = Math.min(hedgeHigh, insHigh);
    if(covHigh > covLow){
      var ix1=toX(covLow),ix2=toX(covHigh);
      ix1=Math.max(ix1, pad.l);
      ix2=Math.min(ix2, pad.l+cW);
      ctx.fillStyle='rgba(63,185,80,0.3)';
      ctx.fillRect(ix1,pad.t,ix2-ix1,cH);
      ctx.strokeStyle='rgba(63,185,80,1.0)';
      ctx.lineWidth=2;ctx.setLineDash([6,4]);
      ctx.beginPath();ctx.moveTo(ix1,pad.t);ctx.lineTo(ix1,pad.t+cH);ctx.stroke();
      ctx.beginPath();ctx.moveTo(ix2,pad.t);ctx.lineTo(ix2,pad.t+cH);ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // X axis line
  ctx.strokeStyle='#30363d';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(pad.l,pad.t+cH);ctx.lineTo(pad.l+cW,pad.t+cH);ctx.stroke();

  // Price labels - only within chart bounds
  ctx.fillStyle='#e6edf3';ctx.font='bold 12px monospace';ctx.textAlign='center';
  allRows.forEach(function(r){
    var x=toX(r.price);
    // Skip if outside chart area
    if(x < pad.l-5 || x > pad.l+cW+5) return;
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
  if(!layer) layer='near';
  var el=document.getElementById('content-'+data.symbol);
  if(!el) return;
  if(!data || !data.rows || data.rows.length===0){
    el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет данных</div>';
    return;
  }

  // Cost per day
  var costPerDay = data.dte > 0 ? (data.entry_premium || 0) / data.dte : 0;

  // Filter rows: 0.5 <= |delta| <= 0.85
  var filtered=[];
  data.rows.forEach(function(r){
    var absD=Math.abs(r.delta);
    if(absD >= 0.5 && absD <= 0.85){
      filtered.push(r);
    }
  });
  if(filtered.length===0){
    el.innerHTML='<div style="color:var(--text-dim);padding:12px;text-align:center">Нет строк в диапазоне Δ 0.5-0.85</div>';
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

  // Insurance range: диапазон работы слоя (3-10% для near и т.д.)
  var hedges={near:{min:3,max:10},mid:{min:8,max:15},distant:{min:15,max:30}};
  var h=hedges[layer]||{min:5,max:20};
  var insLow=Math.round(data.spot*(1-h.max/100));
  var insHigh=Math.round(data.spot*(1-h.min/100));
  var insLen = Math.abs(insHigh - insLow);

  // Coverage: intersection(gamma_range, insurance_range) / insurance_range
  var covLow = Math.max(hedgeLow, insLow);
  var covHigh = Math.min(hedgeHigh, insHigh);
  var covLen = Math.max(0, covHigh - covLow);
  var coverage = insLen > 0 ? covLen / insLen : 0;

  // Accuracy: intersection(gamma_range, insurance_range) / gamma_range
  var accLow = Math.max(hedgeLow, insLow);
  var accHigh = Math.min(hedgeHigh, insHigh);
  var accLen = Math.max(0, accHigh - accLow);
  var accuracy = hedgeLen > 0 ? accLen / hedgeLen : 0;

  // Sum of delta changes in intersection
  var sumDeltaDD = 0;
  for (var i = 1; i < filtered.length; i++) {
    if (filtered[i].price >= covLow && filtered[i].price <= covHigh) {
      sumDeltaDD += filtered[i-1].delta - filtered[i].delta;
    }
  }

  // Sum of gamma in intersection
  var sumGammaInIntersection = 0;
  data.rows.forEach(function(r) {
    if (r.price >= covLow && r.price <= covHigh) {
      sumGammaInIntersection += r.gamma;
    }
  });

  // GammaProtection per Dollar = ΣΓ_intersection / premium
  var gammaProtection = (data.entry_premium || 0) > 0 ? sumGammaInIntersection / data.entry_premium : 0;

  // WeightedPnL = Σ ΔPnL_i × weight_i
  var weightedPnL = 0;
  var spot = Math.round(data.spot);
  var bsMap = {};
  data.rows.forEach(function(r) { bsMap[r.price] = r.bs_price; });
  function bsAt(p) {
    if (bsMap[p] !== undefined) return bsMap[p];
    var lo = null, hi = null;
    for (var k = p; k >= 0; k--) { if (bsMap[k] !== undefined) { lo = k; break; } }
    for (var k = p; k <= spot + 20; k++) { if (bsMap[k] !== undefined) { hi = k; break; } }
    if (lo === null || hi === null) return 0;
    if (lo === hi) return bsMap[lo];
    var frac = (p - lo) / (hi - lo);
    return bsMap[lo] + frac * (bsMap[hi] - bsMap[lo]);
  }
  var prevPnL = bsAt(spot) - (data.entry_premium || 0);
  for (var wi = 1; wi <= spot - covLow; wi++) {
    var p = spot - wi;
    if (p < covLow) break;
    var pnl = bsAt(p) - (data.entry_premium || 0);
    var dPnL = pnl - prevPnL;
    var w = 1.00 - (wi - 1) * 0.05;
    weightedPnL += dPnL * w;
    prevPnL = pnl;
  }

  // Find max gamma
  var maxGammaIdx=-1, maxGamma=-1;
  filtered.forEach(function(r, idx){
    if(r.gamma > maxGamma) { maxGamma=r.gamma; maxGammaIdx=idx; }
  });

  var html='<div style="display:flex;gap:24px;align-items:flex-start">';
  var chartH=380;
  html+='<div style="width:620px;flex-shrink:0"><div style="font-size:14px;font-weight:bold;margin-bottom:6px;color:var(--text-dim)">Профиль Γ</div><div style="border:1px solid var(--border);border-radius:6px;padding:8px;background:var(--surface);height:'+chartH+'px"><canvas id="gammaChart-'+(data.symbol.replace(/[^a-zA-Z0-9]/g,'_'))+'" width="580" height="'+(chartH-24)+'"></canvas></div></div>';
  html+='<div style="height:'+chartH+'px;overflow-y:auto;border:1px solid var(--border);border-radius:6px"><table style="width:540px;border-collapse:collapse;font-size:13px;font-weight:600"><thead><tr style="background:var(--bg);border-bottom:2px solid var(--border);position:sticky;top:0">';
  html+='<th style="text-align:left;padding:4px 6px;font-size:13px">Цена</th><th style="padding:4px 6px;text-align:right;font-size:13px">Δ</th><th style="padding:4px 6px;text-align:right;font-size:13px">Γ</th><th style="padding:4px 6px;text-align:right;font-size:13px">PnL</th><th style="padding:4px 6px;text-align:right;font-size:13px">Вн.стоимость</th><th style="padding:4px 6px;text-align:right;font-size:13px">Врем.стоимость</th></tr></thead><tbody>';
  // Table: ALL prices in working range [hedgeLow, hedgeHigh]
  var tableRows = data.rows.filter(function(r){return r.price >= hedgeLow && r.price <= hedgeHigh;});
  tableRows.forEach(function(r, idx){
    var pnl = r.bs_price - data.entry_premium;
    var pnlCls = pnl >= 0 ? 'color:var(--green)' : 'color:var(--red)';

    var rowBg = '';
    // Highlight max gamma
    if(r.gamma === maxGamma) rowBg='background:rgba(88,166,255,0.15);';

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
  html+='<div style="display:flex;gap:16px;flex-wrap:nowrap">';
  // Column 1: Coverage / Precision
  html+='<div style="flex:1;display:flex;flex-direction:column;gap:8px">';
  html+='<div style="padding:20px 24px;background:var(--surface);border-radius:12px;border:2px solid var(--blue);min-width:160px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:14px">Coverage</div>';
  html+='<div style="color:var(--blue);font-size:32px;font-weight:bold;margin-top:4px">'+(coverage*100).toFixed(0)+'%</div>';
  html+='</div>';
  html+='<div style="padding:14px 18px;background:var(--surface);border-radius:8px;border:1px solid var(--purple);min-width:130px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:11px">Precision</div>';
  html+='<div style="color:var(--purple);font-size:20px;font-weight:bold;margin-top:4px">'+(accuracy*100).toFixed(0)+'%</div>';
  html+='</div>';
  html+='</div>';
  // Column 2: ΣΓ / WeightedPnL
  html+='<div style="flex:1;display:flex;flex-direction:column;gap:8px">';
  html+='<div style="padding:18px 22px;background:var(--surface);border-radius:10px;border:1px solid var(--green);min-width:150px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:13px">ΣΓ в пересечении</div>';
  html+='<div style="color:var(--green);font-size:28px;font-weight:bold;margin-top:4px">'+F(sumGammaInIntersection,6)+'</div>';
  html+='</div>';
  html+='<div style="padding:14px 18px;background:var(--surface);border-radius:8px;border:1px solid var(--magenta);min-width:130px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:11px">WeightedPnL</div>';
  html+='<div style="color:var(--magenta);font-size:20px;font-weight:bold;margin-top:4px">$'+(weightedPnL).toFixed(2)+'</div>';
  html+='</div>';
  html+='</div>';
  // Column 3: Γ/$ / Cost/Day
  html+='<div style="flex:1;display:flex;flex-direction:column;gap:8px">';
  html+='<div style="padding:18px 22px;background:var(--surface);border-radius:10px;border:1px solid var(--cyan);min-width:150px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:13px">Γ/$</div>';
  html+='<div style="color:var(--cyan);font-size:28px;font-weight:bold;margin-top:4px">'+gammaProtection.toFixed(2)+'</div>';
  html+='</div>';
  html+='<div style="padding:12px 16px;background:var(--surface);border-radius:6px;border:1px solid rgba(48,54,61,.6);min-width:110px">';
  html+='<div style="color:var(--text-dim);font-weight:600;font-size:10px">Cost/Day</div>';
  html+='<div style="color:var(--orange);font-size:16px;font-weight:bold;margin-top:4px">$'+(costPerDay).toFixed(2)+'</div>';
  html+='</div>';
  html+='</div>';
  html+='</div>';

  el.innerHTML=html;

  // Draw gamma chart
  var chartId='gammaChart-'+data.symbol.replace(/[^a-zA-Z0-9]/g,'_');
  setTimeout(function(){
    drawGammaChart(data.rows, filtered, data.strike, hedgeLow, hedgeHigh, chartId, [], insLow, insHigh);
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
  console.log('RESET: layer='+layer);
  selectedOption[layer]=[];
  purchasedOptions[layer]=[];
  localStorage.removeItem('selectedOptions');
  layerFilterParams[layer]="all=1";
  fetch(API+'/api/layer/'+layer+'?all=1&refresh=1').then(function(r){
    return r.json();
  }).then(function(data){
    console.log('RESET: count='+data.count);
    renderLayer(data);
  }).catch(function(e){
    console.error('RESET error:', e);
  });
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
    banner.innerHTML = "⛔ <b>Нет данных</b> - Bybit недоступен, снапшотов нет. Проверьте подключение.";
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
    banner.innerHTML = "⚠️ <b>Bybit недоступен</b> - показаны " + ageStr + ". Опционы могут не совпадать с реальностью.";
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
    loadPortfolio();
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
      renderDistantDeltaMatrix();
      renderDistantPnlMatrix();
      renderDistantSummaryMatrix();

      // Build global purchased symbols lookup
      globalPurchasedSymbols={};
      (purchasedOptions.distant||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      (purchasedOptions.mid||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      (purchasedOptions.near||[]).forEach(function(x){globalPurchasedSymbols[x.symbol]=x.qty;});
      // Load global available options
      api("/api/available-options").then(function(d){renderGlobalLayer(d);});
    });
  });
  initAggregator();
  document.getElementById('headerUpdated').textContent='Обновлено: '+new Date().toLocaleTimeString('ru-RU');
  try {
    var sd=JSON.parse(localStorage.getItem('selectedDistant')||'[]');
    if(sd.length>0) selectedOption.distant=sd;
  } catch(e){}
  syncDistantSelected();
  renderDistantGammaChart();
  renderDistantDeltaMatrix();
  renderDistantPnlMatrix();
  renderDistantSummaryMatrix();
}

initAggregator();
loadAll();