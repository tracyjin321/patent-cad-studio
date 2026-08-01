import { CadModelViewer } from "/static/model-viewer.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const HISTORY_KEY = "cad-history";
const HEALTH_CHECK_INTERVAL = 30000;

function renderServiceStatus(state, message) {
  const status = $("#service-status");
  status.className = `status ${state}`;
  status.querySelector("span").textContent = message;
}

async function checkServiceHealth(showChecking = false) {
  if (showChecking) renderServiceStatus("checking", "正在连接生成服务…");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch("/api/health", {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`健康检查返回 ${response.status}`);
    const health = await response.json();
    if (health.status !== "ok") throw new Error("生成服务状态异常");
    renderServiceStatus("online", "生成服务已连接");
  } catch (error) {
    renderServiceStatus("offline", "生成服务暂不可用");
  } finally {
    clearTimeout(timeout);
  }
}

function historySummary(item) {
  const {id,title,part_type,parameters,compliance,parser,parser_detail,step_url,spec_id,spec_url,generation_source,spec_fingerprint,core_elements,time}=item;
  return {id,title,part_type,parameters,compliance,parser,parser_detail,step_url,spec_id,spec_url,generation_source,spec_fingerprint,core_elements,time};
}
function loadHistory() {
  try {
    const parsed=JSON.parse(localStorage.getItem(HISTORY_KEY)||"[]");
    const summaries=(Array.isArray(parsed)?parsed:[]).slice(0,12).map(historySummary);
    localStorage.setItem(HISTORY_KEY,JSON.stringify(summaries));
    return summaries;
  } catch(error) {
    console.warn("历史记录读取失败，已清理本地缓存",error);
    localStorage.removeItem(HISTORY_KEY);
    return [];
  }
}
function persistHistory(items) {
  try {localStorage.setItem(HISTORY_KEY,JSON.stringify(items.slice(0,12).map(historySummary)));return true;}
  catch(error) {console.warn("历史摘要保存失败",error);return false;}
}
const state = { part: "bearing", result: null, zoom: 1, exampleIndex: 0, recommended: new Set(), recommendationSource: "local", recommendationDetail: null, recommendationTimer: null, recommendationController: null, manualSelected: new Set(), manualDeselected: new Set(), history: loadHistory() };
const refreshExamples = [
  "生成深沟球轴承，外径90mm，内径45mm，宽度23mm，包含12个滚珠，用于高速电机转子。",
  "设计调心滚子轴承，外径180mm，内径85mm，宽度41mm，适用于矿山输送机重载支承。",
  "生成平焊法兰，外径160mm，内径76mm，厚度18mm，均布8个直径18mm螺栓孔。",
  "设计高压对焊法兰，公称直径DN100，外径220mm，带颈结构，配置8个连接孔。",
  "构造真空设备连接法兰，外径120mm，内径50mm，密封槽宽6mm，均布6孔。",
  "生成DN50截止阀，阀体长度230mm，总高度310mm，双端法兰连接并包含手轮。",
  "设计电动蝶阀，公称直径DN150，阀板厚度12mm，阀杆直径24mm，法兰式安装。",
  "构造止回阀，公称直径DN80，阀体长度260mm，采用旋启式阀瓣和双端连接。",
  "生成四段阶梯轴，总长360mm，最大直径68mm，包含轴肩、键槽和两端倒角。",
  "设计空心传动轴，总长520mm，外径80mm，内径42mm，两端设置花键连接段。",
  "生成直齿圆柱齿轮，模数3，齿数36，齿宽28mm，中心孔直径32mm并设键槽。",
  "设计重载斜齿轮，模数4，齿数42，螺旋角15度，齿宽45mm，用于减速机。",
  "构造行星齿轮组中的太阳轮，模数2，齿数24，齿宽20mm，中心为花键孔。",
  "生成精密滚珠丝杠，长度600mm，公称直径32mm，导程10mm，两端包含支承轴颈。",
  "设计梯形传动丝杠，长度420mm，直径28mm，导程6mm，单头右旋螺纹。",
  "生成刚性法兰联轴器，外径120mm，总长100mm，轴孔35mm，均布6个连接螺栓。",
  "设计弹性联轴器，外径95mm，总长130mm，两端轴孔分别为28mm和32mm。",
  "构造伺服电机膜片联轴器，外径68mm，总长82mm，轴孔20mm，包含双膜片组。",
  "生成双唇骨架油封，外径72mm，内径40mm，宽度10mm，包含主密封唇和防尘唇。",
  "设计耐高温轴端密封件，外径110mm，内径65mm，宽度16mm，带环形密封槽。"
];
const labels = { bearing:"轴承", flange:"法兰", valve:"阀门", shaft:"轴系", gear:"齿轮", screw:"丝杠", coupling:"联轴器", seal:"密封件" };
const elementPatterns = {
  bearing: /轴承|滚珠|滚子|轴瓦|支承座|bearing/i,
  flange: /法兰|法兰盘|连接盘|突缘|flange/i,
  valve: /阀门|阀体|闸阀|截止阀|蝶阀|球阀|止回阀|调节阀|valve/i,
  shaft: /轴系|主轴|传动轴|输入轴|输出轴|阶梯轴|转轴|轴肩|shaft/i,
  gear: /齿轮|齿圈|轮齿|齿数|模数|gear/i,
  screw: /丝杠|丝杆|螺杆|导程|滚珠丝杠|screw/i,
  coupling: /联轴器|联轴节|轴联接|coupling/i,
  seal: /密封件|密封圈|油封|密封环|密封唇|seal/i
};
const modelViewer = new CadModelViewer($("#model-canvas"));

function selectedParts(){return Object.keys(labels).filter(part=>(state.recommended.has(part)||state.manualSelected.has(part))&&!state.manualDeselected.has(part));}
function renderParts(){
  const selected=new Set(selectedParts());
  $$("#parts button").forEach(button=>{const part=button.dataset.part;button.classList.toggle("active",selected.has(part));button.classList.toggle("recommended",state.recommended.has(part));button.setAttribute("aria-pressed",selected.has(part));button.textContent=labels[part];if(state.recommended.has(part)){const badge=document.createElement("span");badge.className="recommend-badge";badge.textContent="✦";badge.title="智能推荐";badge.setAttribute("aria-label","智能推荐");button.appendChild(badge);}});
  const status=$("#recommendation-status"),recommendedNames=[...state.recommended].map(part=>labels[part]);status.className="";
  if(state.recommendationSource==="loading"){status.classList.add("recognizing");status.innerHTML='<i></i>正在智能识别核心图元<span class="status-dots"><b>.</b><b>.</b><b>.</b></span>';}
  else if(recommendedNames.length){status.classList.add("recognized");status.textContent=`✓ 已推荐：${recommendedNames.join("、")}`;status.title=`已自动推荐 ${recommendedNames.join("、")}，可人工调整`;}
  else if($("#description").value.trim()){status.textContent="未识别到图元，请手动选择";}
  else{status.textContent="自动推荐，可人工补充";}
}
async function fetchModelRecommendations(description){
  state.recommendationController?.abort();const controller=new AbortController(),startedAt=Date.now();state.recommendationController=controller;state.recommendationSource="loading";renderParts();
  const holdLoading=()=>new Promise(resolve=>setTimeout(resolve,Math.max(0,2000-(Date.now()-startedAt))));
  try{const response=await fetch("/api/recommend",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description,use_ai:true}),signal:controller.signal});if(!response.ok)throw new Error(`推荐接口返回 ${response.status}`);const data=await response.json();await holdLoading();if(controller.signal.aborted||$("#description").value!==description)return;state.recommended=new Set(data.elements);state.recommendationSource=data.parser;state.recommendationDetail=data.parser_detail;if(state.recommended.size)state.part=[...state.recommended][0];renderParts();}
  catch(error){if(error.name==="AbortError")return;await holdLoading();if(controller.signal.aborted)return;state.recommendationSource="local-fallback";state.recommendationDetail=error.message;renderParts();}
}
function extractCoreElements(description){clearTimeout(state.recommendationTimer);state.recommendationController?.abort();state.recommended=new Set(Object.entries(elementPatterns).filter(([,pattern])=>pattern.test(description)).map(([part])=>part));state.recommendationSource="local";state.recommendationDetail=null;const current=selectedParts();if(state.recommended.size)state.part=[...state.recommended][0];else if(current.length)state.part=current[0];renderParts();if(description.trim().length>=2&&$("#use-ai").checked)state.recommendationTimer=setTimeout(()=>fetchModelRecommendations(description),500);}

function toast(message) { const el=$("#toast"); el.textContent=message; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2200); }
function setTab(name) { $$(".tabs button").forEach(b=>b.classList.toggle("active",b.dataset.tab===name)); $$(".panel").forEach(p=>p.classList.toggle("active",p.id===name)); }
function renderHistory() {
  const el=$("#history");
  if (!state.history.length) { el.innerHTML='<p class="empty-small">暂无生成记录</p>'; return; }
  const sourceLabel=item=>item.parser==="moonshot"?"Kimi K2.6":item.parser==="local"?"本地解析":`智能解析降级${item.parser_detail?`：${item.parser_detail}`:""}`;
  el.innerHTML=state.history.map((item,i)=>`<div class="history-item" data-index="${i}"><strong>${item.title}</strong><small>${item.time} · ${sourceLabel(item)}${item.svg&&item.model?"":" · 参数摘要"}</small></div>`).join("");
  $$(".history-item").forEach(el=>el.onclick=()=>{const item=state.history[Number(el.dataset.index)];if(item.svg&&item.model)showResult(item);else{renderParams(item);setTab("params");toast("该历史记录仅保留参数摘要，请重新生成预览");}});
}
function renderParams(result) {
  const parserText=result.parser==="moonshot"?"Kimi K2.6 智能解析":result.parser==="local-fallback"?`本地确定性解析（${result.parser_detail||"智能解析暂不可用"}）`:"本地确定性解析";
  const sourceText={generated:"新建 YAML 并物化 STEP",cache:"命中参数化缓存",library:"命中正式图元库"}[result.generation_source]||"旧版直接建模";
  const coreText=(result.core_elements||[result.part_type]).map(part=>labels[part]).join("、");
  $("#parameter-content").innerHTML=`<h2>${result.title}</h2><p>解析方式：${parserText}</p><p>生成规格：${sourceText}${result.spec_id?` · <code>${result.spec_id}</code>`:""}</p><p>核心图元：${coreText}</p><div class="param-grid">${Object.entries(result.parameters).map(([k,v])=>`<div class="param-row"><span>${k.replaceAll("_"," ")}</span><strong>${v}</strong></div>`).join("")}</div><div class="check-list"><h3>合规校验</h3>${result.compliance.map(c=>`<div class="check"><span>${c.name}</span><strong class="${c.passed?"pass":""}">${c.passed?"✓ 通过":"× 未通过"}</strong></div>`).join("")}</div>`;
}
function showResult(result) {
  state.result=result; $("#canvas").classList.remove("empty"); $("#canvas").innerHTML=result.svg; renderParams(result);
  modelViewer.setModel(result.model); $("#step").href=result.step_url; $("#step").classList.remove("disabled");
  if(result.spec_url){$("#yaml").href=result.spec_url;$("#yaml").classList.remove("disabled");}else{$("#yaml").removeAttribute("href");$("#yaml").classList.add("disabled");}
  ["#compliance","#png","#svg"].forEach(id=>$(id).disabled=false); state.zoom=1; applyZoom(); setTab("model");
}
function applyZoom(){ const svg=$("#canvas svg"); if(svg) svg.style.transform=`scale(${state.zoom})`; $("#zoom-label").textContent=`${Math.round(state.zoom*100)}%`; }
function download(blob,name){ const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
async function generate() {
  const description=$("#description").value.trim();
  if(description.length<2){toast("请先输入技术描述");$("#description").focus();return;}
  const coreElements=selectedParts();if(!coreElements.length){toast("请选择至少一个核心图元");return;}const primaryPart=[...state.recommended].find(part=>coreElements.includes(part))||coreElements[0];state.part=primaryPart;
  const button=$("#generate");button.disabled=true;button.classList.add("is-loading");button.setAttribute("aria-busy","true");button.innerHTML='<span class="button-spinner" aria-hidden="true"></span><span>正在生成附图…</span>';
  const progress=$("#generation-progress"), stages=[["正在解析技术描述","识别零件类型、结构尺寸与工程约束…"],["正在生成参数化 YAML","校验生成器、参数约束与规格一致性…"],["正在物化 3D 几何","由 YAML 驱动 OpenCascade 构建 B-Rep…"],["正在输出附图与 STEP","从同一 B-Rep 生成 SVG 附图、3D 预览和 STEP 文件…"]];
  let progressValue=0;
  const renderProgress=()=>{const stage=progressValue<28?0:progressValue<54?1:progressValue<79?2:3;const [title,detail]=stages[stage];progress.dataset.stage=stage;$$('.cad-phases span').forEach((item,index)=>{item.classList.toggle("active",index===stage);item.classList.toggle("done",index<stage)});$("#progress-bar").style.width=`${progressValue}%`;$("#progress-percent").textContent=`${Math.round(progressValue)}%`;$("#progress-title").textContent=title;$("#progress-detail").textContent=detail;};
  progress.classList.add("show");renderProgress();const timer=setInterval(()=>{const remaining=96-progressValue;progressValue=Math.min(96,progressValue+Math.max(.18,remaining*.022));renderProgress();},120);
  $("#canvas").classList.remove("empty");$("#canvas").innerHTML='<div class="spinner"></div>';
  try {
    const response=await fetch("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description,part_type:primaryPart,core_elements:coreElements,field:$("#field").value,use_ai:$("#use-ai").checked})});
    if(!response.ok) throw new Error(`附图生成失败（错误码：${response.status}）`);
    const result=await response.json();clearInterval(timer);progressValue=100;progress.dataset.stage="4";$$('.cad-phases span').forEach(item=>{item.classList.remove("active");item.classList.add("done")});$("#progress-bar").style.width="100%";$("#progress-percent").textContent="100%";$("#progress-title").textContent="生成完成";$("#progress-detail").textContent="SVG 附图、3D 预览与 STEP 文件已就绪";await new Promise(r=>setTimeout(r,600));result.time=new Date().toLocaleString("zh-CN",{hour12:false});
    state.history.unshift(result);state.history=state.history.slice(0,12);renderHistory();showResult(result);persistHistory(state.history);toast("附图已生成");
  } catch(error) { $("#canvas").classList.add("empty");$("#canvas").innerHTML=`<div class="placeholder"><p>${error.message}</p><small>请稍后重试；如问题持续，请联系管理员</small></div>`;toast(error.message); }
  finally {clearInterval(timer);progress.classList.remove("show");button.disabled=false;button.classList.remove("is-loading");button.removeAttribute("aria-busy");button.innerHTML='<svg class="ui-icon" aria-hidden="true"><use href="#icon-sparkles"></use></svg><span>生成附图</span>';}
}

$("#description").oninput=e=>{$("#counter").textContent=`${e.target.value.length}/5000`;extractCoreElements(e.target.value);};
$("#example").onclick=()=>{const index=state.exampleIndex%refreshExamples.length;$("#description").value=refreshExamples[index];state.exampleIndex=(index+1)%refreshExamples.length;$("#description").dispatchEvent(new Event("input"));};
$("#clear").onclick=()=>{$("#description").value="";$("#description").dispatchEvent(new Event("input"));};
$("#parts").onclick=e=>{const button=e.target.closest("button");if(!button)return;const part=button.dataset.part;const selected=selectedParts().includes(part);if(selected){state.manualSelected.delete(part);if(state.recommended.has(part))state.manualDeselected.add(part);}else{state.manualDeselected.delete(part);state.manualSelected.add(part);state.part=part;}renderParts();};
$("#document").onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>2*1024*1024){toast("文件不能超过 2MB");return;}$("#description").value=await file.text();$("#description").dispatchEvent(new Event("input"));toast("文档已导入");};
$("#use-ai").onchange=()=>extractCoreElements($("#description").value);
$("#generate").onclick=generate;
$$(".tabs button").forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
$("#zoom-in").onclick=()=>{state.zoom=Math.min(1.8,state.zoom+.1);applyZoom();};
$("#zoom-out").onclick=()=>{state.zoom=Math.max(.5,state.zoom-.1);applyZoom();};
$("#reset").onclick=()=>{state.zoom=1;applyZoom();};
$("#compliance").onclick=()=>{setTab("params");toast(state.result.compliance.every(c=>c.passed)?"全部合规检查通过":"存在未通过项目");};
$("#svg").onclick=()=>download(new Blob([state.result.svg],{type:"image/svg+xml"}),`${state.result.part_type}-${state.result.id.slice(0,8)}.svg`);
$("#png").onclick=()=>{const image=new Image();const blob=new Blob([state.result.svg],{type:"image/svg+xml"});const url=URL.createObjectURL(blob);image.onload=()=>{const canvas=document.createElement("canvas");canvas.width=2480;canvas.height=3508;canvas.getContext("2d").drawImage(image,0,0,2480,3508);canvas.toBlob(png=>download(png,`${state.result.part_type}-${state.result.id.slice(0,8)}.png`));URL.revokeObjectURL(url);};image.src=url;};
$("#clear-history").onclick=()=>{state.history=[];localStorage.removeItem(HISTORY_KEY);renderHistory();toast("历史记录已清空");};
renderHistory();
renderParts();
checkServiceHealth(true);
setInterval(checkServiceHealth, HEALTH_CHECK_INTERVAL);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") checkServiceHealth();
});
