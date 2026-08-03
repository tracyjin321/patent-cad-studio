import { CadModelViewer } from "/static/model-viewer.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const HISTORY_KEY = "cad-history";
const HISTORY_VISIBLE_LIMIT = 5;
const HISTORY_STORAGE_LIMIT = 50;
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
    if(state.isGenerating)renderServiceStatus("busy", "正在执行几何建模");
    else renderServiceStatus("offline", "生成服务暂不可用");
  } finally {
    clearTimeout(timeout);
  }
}

function historySummary(item) {
  const {id,title,part_type,parameters,structural_parameters,compliance,parser,parser_detail,step_url,spec_id,spec_url,generation_source,spec_fingerprint,core_elements,selected_components,time}=item;
  return {id,title,part_type,parameters,structural_parameters,compliance,parser,parser_detail,step_url,spec_id,spec_url,generation_source,spec_fingerprint,core_elements,selected_components,time};
}
function loadHistory() {
  try {
    const parsed=JSON.parse(localStorage.getItem(HISTORY_KEY)||"[]");
    const summaries=(Array.isArray(parsed)?parsed:[]).slice(0,HISTORY_STORAGE_LIMIT).map(historySummary);
    localStorage.setItem(HISTORY_KEY,JSON.stringify(summaries));
    return summaries;
  } catch(error) {
    console.warn("历史记录读取失败，已清理本地缓存",error);
    localStorage.removeItem(HISTORY_KEY);
    return [];
  }
}
function persistHistory(items) {
  try {localStorage.setItem(HISTORY_KEY,JSON.stringify(items.slice(0,HISTORY_STORAGE_LIMIT).map(historySummary)));return true;}
  catch(error) {console.warn("历史摘要保存失败",error);return false;}
}
const state = { part: "bearing", result: null, referenceImage: null, isGenerating: false, zoom: 1, exampleIndex: 0, recommended: new Set(), recommendationSource: "local", recommendationDetail: null, recommendationTimer: null, recommendationController: null, components: [], componentIndex: new Map(), componentCategories: [], selectedComponentIds: new Set(), componentQueryTimer: null, componentController: null, history: loadHistory(), historyExpanded: false };
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
  "设计耐高温轴端密封件，外径110mm，内径65mm，宽度16mm，带环形密封槽。",
  "生成猎鹰九号 Block 5 全箭，火箭总高度70米，箭体直径3.66米，整流罩直径5.2米，配置9台Merlin发动机、4片栅格翼和4条折叠着陆腿。"
];
const labels = { bearing:"轴承", flange:"法兰", valve:"阀门", shaft:"轴系", gear:"齿轮", screw:"丝杠", coupling:"联轴器", seal:"密封件", rocket:"运载火箭" };
const elementPatterns = {
  bearing: /轴承|滚珠|滚子|轴瓦|支承座|bearing/i,
  flange: /法兰|法兰盘|连接盘|突缘|flange/i,
  valve: /阀门|阀体|闸阀|截止阀|蝶阀|球阀|止回阀|调节阀|valve/i,
  shaft: /轴系|主轴|传动轴|输入轴|输出轴|阶梯轴|转轴|轴肩|shaft/i,
  gear: /齿轮|齿圈|轮齿|齿数|模数|gear/i,
  screw: /丝杠|丝杆|螺杆|导程|滚珠丝杠|screw/i,
  coupling: /联轴器|联轴节|轴联接|coupling/i,
  seal: /密封件|密封圈|油封|密封环|密封唇|seal/i,
  rocket: /猎鹰九号|猎鹰9号|Falcon\s*9|运载火箭|火箭/i
};
const componentTypeToPart = {bearing:"bearing",shaft:"shaft",hub:"shaft",gear:"gear",pulley:"gear",sprocket:"gear",screw:"screw",nut:"screw",coupling:"coupling",seal:"seal",flange:"flange",valve:"valve",rocket:"rocket"};
const componentIconPaths = {
  fastener:'<path d="M12 2 7 5v5l3 2v10h4V12l3-2V5Z"/><path d="M8 6h8M10 14h4M10 17h4M10 20h4"/>',
  nut:'<path d="m5 8 4-4h6l4 4v8l-4 4H9l-4-4Z"/><circle cx="12" cy="12" r="3"/>',
  spacer:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
  bearing:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="5.5" r="1"/><circle cx="18.5" cy="12" r="1"/><circle cx="12" cy="18.5" r="1"/><circle cx="5.5" cy="12" r="1"/>',
  gear:'<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/><circle cx="12" cy="12" r="8"/>',
  pulley:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M6.5 7.5c3 2 8 2 11 0M6.5 16.5c3-2 8-2 11 0"/>',
  screw:'<path d="M5 17 17 5l2 2L7 19Z"/><path d="m14 6 4 4M7 15l2 2M9 13l2 2M11 11l2 2"/>',
  shaft:'<path d="M3 10h15l3 2-3 2H3Z"/><path d="M7 10v4M17 10v4"/>',
  coupling:'<path d="M3 9h7v6H3ZM14 9h7v6h-7Z"/><path d="M10 11h4M10 13h4"/>',
  pin:'<path d="M5 15 17 5l2 2L7 17Z"/><circle cx="6" cy="16" r="2"/>',
  actuator:'<rect x="4" y="7" width="12" height="10" rx="2"/><path d="M16 10h5v4h-5M8 7V4M12 7V4"/>',
  profile:'<path d="M4 4h16v4h-6v8h6v4H4v-4h6V8H4Z"/>',
  stock:'<path d="m4 7 8-4 8 4-8 4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/>',
  motion:'<path d="M3 8h18v8H3Z"/><path d="M7 8v8M17 8v8M5 5h14M7 3 5 5l2 2M17 3l2 2-2 2"/>',
  hardware:'<path d="M5 4h14v16H5Z"/><path d="M9 4v16M15 4v16M5 9h14M5 15h14"/>'
};
function componentIcon(type){const icon=document.createElement("span");icon.className="component-icon";icon.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${componentIconPaths[type]||componentIconPaths.stock}</svg>`;return icon;}
const modelViewer = new CadModelViewer($("#model-canvas"));

function selectedParts(){const explicit=[...state.selectedComponentIds].map(id=>componentTypeToPart[state.componentIndex.get(id)?.type]).filter(Boolean);return [...new Set([...explicit,...state.recommended])];}
function renderPrimaryPartControl(parts){
  const selector=$("#primary-part"),hint=$("#primary-part-hint");
  if(!parts.length){selector.innerHTML="<option>语义自动匹配</option>";selector.disabled=true;hint.textContent="未选择图元时，将根据技术描述自动确定主要生成对象。";return;}
  if(!parts.includes(state.part))state.part=parts[0];
  selector.disabled=false;selector.innerHTML=parts.map(part=>`<option value="${part}">${labels[part]}</option>`).join("");selector.value=state.part;
  const related=parts.filter(part=>part!==state.part).map(part=>labels[part]);
  hint.textContent=related.length?`已选图元：${[labels[state.part],...related].join("、")}。当前以${labels[state.part]}为主要生成对象。`:`当前以${labels[state.part]}为主要生成对象。`;
}
function renderRecommendation(){
  const status=$("#recommendation-status"),recommendedNames=[...state.recommended].map(part=>labels[part]);status.className="";
  status.classList.add("component-recommendation");
  if(state.recommendationSource==="loading"){status.classList.add("recognizing");status.innerHTML='<i></i>正在智能识别核心图元<span class="status-dots"><b>.</b><b>.</b><b>.</b></span>';}
  else if(recommendedNames.length){status.classList.add("recognized");status.textContent=`✓ 已推荐：${recommendedNames.join("、")}`;status.title=`已自动推荐 ${recommendedNames.join("、")}，可人工调整`;}
  else if($("#description").value.trim()){status.textContent="暂未识别到匹配类型，可直接选择图元";}
  else{status.textContent="未选择时将根据技术描述自动匹配";}
  renderPrimaryPartControl(selectedParts());
}
async function fetchModelRecommendations(description){
  state.recommendationController?.abort();const controller=new AbortController(),startedAt=Date.now();state.recommendationController=controller;state.recommendationSource="loading";renderRecommendation();
  const holdLoading=()=>new Promise(resolve=>setTimeout(resolve,Math.max(0,2000-(Date.now()-startedAt))));
  try{const response=await fetch("/api/recommend",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description,use_ai:true}),signal:controller.signal});if(!response.ok)throw new Error(`推荐接口返回 ${response.status}`);const data=await response.json();await holdLoading();if(controller.signal.aborted||$("#description").value!==description)return;state.recommended=new Set(data.elements);state.recommendationSource=data.parser;state.recommendationDetail=data.parser_detail;if(state.recommended.size)state.part=[...state.recommended][0];renderRecommendation();renderComponents();}
  catch(error){if(error.name==="AbortError")return;await holdLoading();if(controller.signal.aborted)return;state.recommendationSource="local-fallback";state.recommendationDetail=error.message;renderRecommendation();}
}
function extractCoreElements(description){clearTimeout(state.recommendationTimer);state.recommendationController?.abort();state.recommended=new Set(Object.entries(elementPatterns).filter(([,pattern])=>pattern.test(description)).map(([part])=>part));state.recommendationSource="local";state.recommendationDetail=null;const current=selectedParts();if(state.recommended.size)state.part=[...state.recommended][0];else if(current.length)state.part=current[0];renderRecommendation();renderComponents();if(description.trim().length>=2&&$("#use-ai").checked)state.recommendationTimer=setTimeout(()=>fetchModelRecommendations(description),500);}

function renderComponents(){
  const container=$("#component-groups");container.replaceChildren();
  $("#component-selection-count").textContent=`（可选，${state.selectedComponentIds.size} 已选）`;
  if(!state.components.length){const empty=document.createElement("p");empty.className="empty-small";empty.textContent="没有找到匹配图元";container.appendChild(empty);return;}
  const groups=state.components.reduce((map,item)=>{const list=map.get(item.category)||[];list.push(item);map.set(item.category,list);return map;},new Map());
  for(const [category,components] of groups){
    const group=document.createElement("section");group.className="component-group";
    const title=document.createElement("div");title.className="component-group-title";const strong=document.createElement("strong"),categoryIndex=state.componentCategories.findIndex(item=>item.id===category);strong.textContent=`${String(Math.max(0,categoryIndex)+1).padStart(2,"0")} ${components[0].category_label}`;const count=document.createElement("span");count.textContent=components.length;title.append(strong,count);group.appendChild(title);
    const grid=document.createElement("div");grid.className="component-grid";
    for(const component of components){const button=document.createElement("button");button.type="button";button.className="component-card";button.dataset.componentId=component.id;const selected=state.selectedComponentIds.has(component.id),part=componentTypeToPart[component.type];button.classList.toggle("selected",selected);button.classList.toggle("recommended",Boolean(part&&state.recommended.has(part)));button.setAttribute("aria-pressed",String(selected));button.setAttribute("aria-label",`${component.name}，悬停查看详情`);const text=document.createElement("span");text.className="component-card-text";const name=document.createElement("strong");name.textContent=component.name;const code=document.createElement("small");code.textContent=component.id;text.append(name,code);const detail=document.createElement("span");detail.className="component-card-detail";const detailTitle=document.createElement("strong");detailTitle.textContent=component.name;const english=document.createElement("span");english.textContent=component.name_en||"暂无英文原名";const meta=document.createElement("small");meta.textContent=`${component.subtype_label||component.type} · v${component.version||"1.0.0"}`;const description=document.createElement("small");description.textContent=component.description||"component_library 标准装配图元";detail.append(detailTitle,english,meta,description);button.append(componentIcon(component.type),text,detail);grid.appendChild(button);}
    group.appendChild(grid);container.appendChild(group);
  }
}
async function loadComponents(){
  state.componentController?.abort();const controller=new AbortController();state.componentController=controller;const params=new URLSearchParams();const q=$("#component-search").value.trim(),category=$("#component-category").value;if(q)params.set("q",q);if(category)params.set("category",category);
  try{const response=await fetch(`/api/components?${params}`,{signal:controller.signal});if(!response.ok)throw new Error(`图元目录加载失败 (${response.status})`);const data=await response.json();state.components=data.items;for(const component of data.items)state.componentIndex.set(component.id,component);if(!state.componentCategories.length){state.componentCategories=data.categories;for(const item of data.categories){const option=document.createElement("option");option.value=item.id;option.textContent=`${item.label} (${item.count})`;$("#component-category").appendChild(option);}}renderComponents();}
  catch(error){if(error.name==="AbortError")return;$("#component-groups").innerHTML='<p class="empty-small">component_library 暂时无法加载</p>';toast(error.message);}
}

function toast(message) { const el=$("#toast"); el.textContent=message; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2200); }
function setTab(name) { $$(".tabs button").forEach(b=>b.classList.toggle("active",b.dataset.tab===name)); $$(".panel").forEach(p=>p.classList.toggle("active",p.id===name)); }
function renderHistory() {
  const el=$("#history");
  if (!state.history.length) { el.innerHTML='<p class="empty-small">暂无生成记录</p>'; return; }
  const sourceLabel=item=>item.parser==="moonshot"?"Kimi K2.6":item.parser==="local"?"本地解析":`智能解析降级${item.parser_detail?`：${item.parser_detail}`:""}`;
  const visible=state.historyExpanded?state.history:state.history.slice(0,HISTORY_VISIBLE_LIMIT),remaining=Math.max(0,state.history.length-HISTORY_VISIBLE_LIMIT);
  const items=visible.map((item,i)=>`<div class="history-item" data-index="${i}"><strong>${item.title}</strong><small>${item.time} · ${sourceLabel(item)}${item.svg&&item.model?"":" · 参数摘要"}</small></div>`).join("");
  const more=remaining?`<button type="button" class="history-more" aria-expanded="${state.historyExpanded}"><span class="history-more-label">${state.historyExpanded?"收起历史记录":"展开更多"}</span>${state.historyExpanded?"":`<span class="history-more-count">${remaining}</span>`}<i class="history-more-chevron" aria-hidden="true"></i></button>`:"";
  el.innerHTML=items+more;
  el.querySelectorAll(".history-item").forEach(itemEl=>itemEl.onclick=()=>{const item=state.history[Number(itemEl.dataset.index)];if(item.svg&&item.model)showResult(item);else{renderParams(item);setTab("params");toast("该历史记录仅保留参数摘要，请重新生成预览");}});
  el.querySelector(".history-more")?.addEventListener("click",()=>{state.historyExpanded=!state.historyExpanded;renderHistory();});
}
function renderParams(result) {
  const parserText=result.parser==="moonshot"?"Kimi K2.6 智能解析":"本地确定性解析",parserDetail=result.parser==="local-fallback"?`<p>解析说明：${result.parser_detail||"智能解析暂不可用，已自动回退"}</p>`:"";
  const sourceText={generated:"新建 YAML 并物化 STEP",cache:"命中参数化缓存",library:"命中正式图元库"}[result.generation_source]||"旧版直接建模";
  const selectedComponents=result.selected_components||[];const coreText=selectedComponents.length?selectedComponents.map(component=>component.name).join("、"):(result.core_elements||[result.part_type]).map(part=>labels[part]).join("、")+"（语义自动匹配）";
  const documentedParameters={...result.parameters,...(result.structural_parameters||{})};
  $("#parameter-content").innerHTML=`<h2>${result.title}</h2><p>解析方式：${parserText}</p>${parserDetail}<p>生成规格：${sourceText}${result.spec_id?` · <code>${result.spec_id}</code>`:""}</p><p>核心图元：${coreText}</p><div class="param-grid">${Object.entries(documentedParameters).map(([k,v])=>`<div class="param-row"><span>${k.replaceAll("_"," ")}</span><strong>${v}</strong></div>`).join("")}</div><div class="check-list"><h3>合规校验</h3>${result.compliance.map(c=>`<div class="check"><span>${c.name}</span><strong class="${c.passed?"pass":""}">${c.passed?"✓ 通过":"× 未通过"}</strong></div>`).join("")}</div>`;
}
function showResult(result) {
  state.result=result; $("#canvas").classList.remove("empty"); $("#canvas").innerHTML=result.svg; renderParams(result);
  modelViewer.setModel(result.model); $("#step").href=result.step_url; $("#step").classList.remove("disabled");
  if(result.spec_url){$("#yaml").href=result.spec_url;$("#yaml").classList.remove("disabled");}else{$("#yaml").removeAttribute("href");$("#yaml").classList.add("disabled");}
  const compliancePassed=result.compliance.length>0&&result.compliance.every(check=>check.passed),complianceButton=$("#compliance");
  complianceButton.disabled=false;complianceButton.classList.toggle("is-passed",compliancePassed);complianceButton.title=compliancePassed?"全部基础校验通过":"存在未通过的基础校验项目";
  ["#png","#svg"].forEach(id=>$(id).disabled=false); state.zoom=1; applyZoom(); setTab("model");
}
function applyZoom(){ const svg=$("#canvas svg"); if(svg) svg.style.transform=`scale(${state.zoom})`; $("#zoom-label").textContent=`${Math.round(state.zoom*100)}%`; }
function download(blob,name){ const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
async function generate() {
  const description=$("#description").value.trim();
  if(description.length<2){toast("请先输入技术描述");$("#description").focus();return;}
  const coreElements=selectedParts();const primaryPart=coreElements.includes(state.part)?state.part:coreElements[0]||state.part||"bearing";state.part=primaryPart;
  state.isGenerating=true;renderServiceStatus("busy","正在执行几何建模");
  $("#compliance").disabled=true;$("#compliance").classList.remove("is-passed");$("#compliance").removeAttribute("title");
  const button=$("#generate");button.disabled=true;button.classList.add("is-loading");button.setAttribute("aria-busy","true");button.innerHTML='<span class="button-spinner" aria-hidden="true"></span><span>正在生成附图…</span>';
  const progress=$("#generation-progress"), stages=[["正在解析技术描述","识别零件类型、结构尺寸与工程约束…"],["正在生成参数化 YAML","校验生成器、参数约束与规格一致性…"],["正在物化 3D 几何","由 YAML 驱动 OpenCascade 构建 B-Rep；复杂螺旋可能需要约 1 分钟…"],["正在输出附图与 STEP","从同一 B-Rep 生成 SVG 附图、3D 预览和 STEP 文件…"]];
  let progressValue=0;
  const renderProgress=()=>{const stage=progressValue<28?0:progressValue<54?1:progressValue<79?2:3;const [title,detail]=stages[stage];progress.dataset.stage=stage;$$('.cad-phases span').forEach((item,index)=>{item.classList.toggle("active",index===stage);item.classList.toggle("done",index<stage)});$("#progress-bar").style.width=`${progressValue}%`;$("#progress-percent").textContent=progressValue>=95?"处理中":`${Math.round(progressValue)}%`;$("#progress-title").textContent=title;$("#progress-detail").textContent=detail;};
  progress.classList.add("show");renderProgress();const timer=setInterval(()=>{const remaining=96-progressValue;progressValue=Math.min(96,progressValue+Math.max(.18,remaining*.022));renderProgress();},120);
  $("#canvas").classList.remove("empty");$("#canvas").innerHTML='<div class="spinner"></div>';
  try {
    const response=await fetch("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description,part_type:primaryPart,core_elements:coreElements,component_ids:[...state.selectedComponentIds],use_ai:$("#use-ai").checked})});
    if(!response.ok) throw new Error(`附图生成失败（错误码：${response.status}）`);
    const result=await response.json();clearInterval(timer);progressValue=100;progress.dataset.stage="4";$$('.cad-phases span').forEach(item=>{item.classList.remove("active");item.classList.add("done")});$("#progress-bar").style.width="100%";$("#progress-percent").textContent="100%";$("#progress-title").textContent="生成完成";$("#progress-detail").textContent="SVG 附图、3D 预览与 STEP 文件已就绪";await new Promise(r=>setTimeout(r,600));result.time=new Date().toLocaleString("zh-CN",{hour12:false});
    state.history.unshift(result);state.history=state.history.slice(0,HISTORY_STORAGE_LIMIT);state.historyExpanded=false;renderHistory();showResult(result);persistHistory(state.history);toast("附图已生成");
  } catch(error) { $("#canvas").classList.add("empty");$("#canvas").innerHTML=`<div class="placeholder"><p>${error.message}</p><small>请稍后重试；如问题持续，请联系管理员</small></div>`;toast(error.message); }
  finally {clearInterval(timer);progress.classList.remove("show");button.disabled=false;button.classList.remove("is-loading");button.removeAttribute("aria-busy");button.innerHTML='<span>生成附图</span>';state.isGenerating=false;checkServiceHealth();}
}

$("#description").oninput=e=>{$("#counter").textContent=`${e.target.value.length}/5000`;extractCoreElements(e.target.value);};
$("#example").onclick=()=>{const index=state.exampleIndex%refreshExamples.length;$("#description").value=refreshExamples[index];state.exampleIndex=(index+1)%refreshExamples.length;$("#description").dispatchEvent(new Event("input"));};
$("#clear").onclick=()=>{$("#description").value="";$("#description").dispatchEvent(new Event("input"));};
$("#component-toggle").onclick=()=>{const open=$("#component-toggle").getAttribute("aria-expanded")==="true";$("#component-toggle").setAttribute("aria-expanded",String(!open));$("#component-panel").hidden=open;};
$("#component-groups").onclick=e=>{const button=e.target.closest("[data-component-id]");if(!button)return;const id=button.dataset.componentId;if(state.selectedComponentIds.has(id))state.selectedComponentIds.delete(id);else state.selectedComponentIds.add(id);renderComponents();renderRecommendation();};
$("#component-search").oninput=()=>{clearTimeout(state.componentQueryTimer);state.componentQueryTimer=setTimeout(loadComponents,220);};
$("#component-category").onchange=loadComponents;
$("#primary-part").onchange=e=>{state.part=e.target.value;renderPrimaryPartControl(selectedParts());};
$("#document").onchange=async e=>{const input=e.target,file=input.files[0];if(!file)return;if(file.size>10*1024*1024){input.value="";toast("文档不能超过 10MB");return;}const form=new FormData();form.append("file",file);try{const response=await fetch("/api/documents/extract",{method:"POST",body:form}),data=await response.json();if(!response.ok)throw new Error(data.detail||"文档解析失败");$("#description").value=data.text;$("#description").dispatchEvent(new Event("input"));toast(data.truncated?"文档已导入，超长内容已截取前 5000 字":"文档已导入");}catch(error){input.value="";toast(error.message);}};
$("#reference-image").onchange=e=>{const input=e.target,file=input.files[0],label=$("#reference-image-label"),allowed=new Set(["image/png","image/jpeg","image/webp"]);if(!file){state.referenceImage=null;label.textContent="点击上传参考图片";label.removeAttribute("title");return;}if(!allowed.has(file.type)){input.value="";state.referenceImage=null;label.textContent="点击上传参考图片";toast("请选择 PNG、JPG 或 WebP 图片");return;}if(file.size>5*1024*1024){input.value="";state.referenceImage=null;label.textContent="点击上传参考图片";toast("图片不能超过 5MB");return;}state.referenceImage=file;label.textContent=file.name;label.title=file.name;toast("参考图片已选择");};
$("#use-ai").onchange=()=>extractCoreElements($("#description").value);
$("#generate").onclick=generate;
$$(".tabs button").forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
$("#zoom-in").onclick=()=>{state.zoom=Math.min(1.8,state.zoom+.1);applyZoom();};
$("#zoom-out").onclick=()=>{state.zoom=Math.max(.5,state.zoom-.1);applyZoom();};
$("#reset").onclick=()=>{state.zoom=1;applyZoom();};
$("#compliance").onclick=()=>{setTab("params");toast(state.result.compliance.every(c=>c.passed)?"全部合规检查通过":"存在未通过项目");};
$("#svg").onclick=()=>download(new Blob([state.result.svg],{type:"image/svg+xml"}),`${state.result.part_type}-${state.result.id.slice(0,8)}.svg`);
$("#png").onclick=()=>{const image=new Image();const blob=new Blob([state.result.svg],{type:"image/svg+xml"});const url=URL.createObjectURL(blob);image.onload=()=>{const canvas=document.createElement("canvas");canvas.width=2480;canvas.height=3508;canvas.getContext("2d").drawImage(image,0,0,2480,3508);canvas.toBlob(png=>download(png,`${state.result.part_type}-${state.result.id.slice(0,8)}.png`));URL.revokeObjectURL(url);};image.src=url;};
$("#clear-history").onclick=()=>{state.history=[];state.historyExpanded=false;localStorage.removeItem(HISTORY_KEY);renderHistory();toast("历史记录已清空");};
renderHistory();
renderRecommendation();
loadComponents();
checkServiceHealth(true);
setInterval(checkServiceHealth, HEALTH_CHECK_INTERVAL);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") checkServiceHealth();
});
