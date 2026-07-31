import { CadModelViewer } from "/static/model-viewer.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { part: "bearing", result: null, zoom: 1, exampleIndex: {}, history: JSON.parse(localStorage.getItem("cad-history") || "[]") };
const examples = {
  bearing: ["生成一个深沟球轴承，外径100mm，内径45mm，宽度25mm，包含10个滚动体，用于高速传动轴支撑。","设计重载圆柱滚子轴承，外径160mm，内径80mm，宽度38mm，12个滚动体，用于减速箱输出端。","生成紧凑型轴承，外径72mm，内径30mm，宽度19mm，8个滚珠，适合电机转子。","设计风机主轴轴承，外径220mm，内径110mm，宽度48mm，14个滚动体。","生成精密机床轴承，外径125mm，内径60mm，宽度28mm，12个滚珠。"],
  flange: ["生成管道连接法兰，外径180mm，内径80mm，厚22mm，均布8个螺栓孔。","设计高压法兰，外径240mm，通孔100mm，厚度32mm，12个螺栓孔。","生成小型设备法兰，外径120mm，内径50mm，厚16mm，6孔均布。","设计泵体连接法兰，外径300mm，内径150mm，厚度40mm，16个安装孔。","生成真空管路法兰，外径95mm，内径40mm，厚度12mm，4个螺栓孔。"],
  valve: ["生成公称直径80mm的截止阀，阀体长度210mm，总高度240mm，双端法兰连接。","设计公称直径50mm的闸阀，阀体长180mm，总高260mm，用于蒸汽管线。","生成公称直径100mm的调节阀，阀体长度260mm，总高320mm。","设计公称直径150mm的海水蝶阀，阀体长度320mm，总高度380mm。","生成公称直径40mm的实验室针阀，阀体长度130mm，总高度170mm。"],
  shaft: ["生成四段阶梯轴，总长280mm，最大直径70mm，带12mm宽键槽。","设计减速机输入轴，总长340mm，最大直径85mm，五段轴肩，键槽宽14mm。","生成电机输出轴，总长190mm，最大直径48mm，三段轴肩，键槽宽10mm。","设计轧机传动轴，总长620mm，最大直径140mm，六段轴肩，键槽宽24mm。","生成机器人关节轴，总长150mm，最大直径38mm，四段轴肩，键槽宽8mm。"],
  gear: ["生成模数3、齿数24的直齿圆柱齿轮，中心孔32mm，齿宽28mm。","设计模数5、齿数36的重载直齿轮，中心孔60mm，齿宽45mm。","生成模数2、齿数48的精密齿轮，孔径20mm，齿宽18mm。","设计模数4、齿数18的小齿轮，中心孔35mm，齿宽40mm。","生成模数1.5、齿数64的仪表齿轮，中心孔12mm，齿宽10mm。"],
  screw: ["生成长度300mm、直径32mm、导程10mm的单头精密丝杠。","设计长度500mm、直径40mm、导程12mm的双头传动丝杠。","生成长度220mm、直径20mm、导程5mm的定位丝杠。","设计长度800mm、直径50mm、导程16mm的重载升降丝杠。","生成长度160mm、直径16mm、导程4mm的微型执行器丝杠。"],
  coupling: ["生成外径96mm、长度120mm、孔径32mm、6螺栓法兰联轴器。","设计外径150mm、总长180mm、轴孔55mm、8螺栓重载联轴器。","生成外径72mm、长度90mm、孔径24mm、4螺栓紧凑联轴器。","设计外径210mm、长度240mm、轴孔80mm、10螺栓船用联轴器。","生成外径58mm、长度68mm、孔径16mm、4螺栓伺服联轴器。"],
  seal: ["生成外径85mm、内径55mm、宽12mm的双唇密封件。","设计外径120mm、内径80mm、宽度15mm的耐压双唇油封。","生成外径62mm、内径40mm、宽8mm的单唇旋转密封件。","设计外径180mm、内径130mm、宽度20mm的重载轴端密封件。","生成外径42mm、内径24mm、宽7mm的微型电机防尘密封件。"]
};
const labels = { bearing:"轴承", flange:"法兰", valve:"阀门", shaft:"轴系", gear:"齿轮", screw:"丝杠", coupling:"联轴器", seal:"密封件" };
const modelViewer = new CadModelViewer($("#model-canvas"));

function toast(message) { const el=$("#toast"); el.textContent=message; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2200); }
function setTab(name) { $$(".tabs button").forEach(b=>b.classList.toggle("active",b.dataset.tab===name)); $$(".panel").forEach(p=>p.classList.toggle("active",p.id===name)); }
function renderHistory() {
  const el=$("#history");
  if (!state.history.length) { el.innerHTML='<p class="empty-small">暂无生成记录</p>'; return; }
  const sourceLabel=item=>item.parser==="moonshot"?"Kimi K2.6":item.parser==="local"?"本地解析":`智能解析降级${item.parser_detail?`：${item.parser_detail}`:""}`;
  el.innerHTML=state.history.map((item,i)=>`<div class="history-item" data-index="${i}"><strong>${item.title}</strong><small>${item.time} · ${sourceLabel(item)}</small></div>`).join("");
  $$(".history-item").forEach(el=>el.onclick=()=>showResult(state.history[Number(el.dataset.index)]));
}
function renderParams(result) {
  const parserText=result.parser==="moonshot"?"Kimi K2.6 智能解析":result.parser==="local-fallback"?`本地确定性解析（${result.parser_detail||"智能解析暂不可用"}）`:"本地确定性解析";
  $("#parameter-content").innerHTML=`<h2>${result.title}</h2><p>解析方式：${parserText}</p><div class="param-grid">${Object.entries(result.parameters).map(([k,v])=>`<div class="param-row"><span>${k.replaceAll("_"," ")}</span><strong>${v}</strong></div>`).join("")}</div><div class="check-list"><h3>合规校验</h3>${result.compliance.map(c=>`<div class="check"><span>${c.name}</span><strong class="${c.passed?"pass":""}">${c.passed?"✓ 通过":"× 未通过"}</strong></div>`).join("")}</div>`;
}
function showResult(result) {
  state.result=result; $("#canvas").classList.remove("empty"); $("#canvas").innerHTML=result.svg; renderParams(result);
  modelViewer.setModel(result.model); $("#step").href=result.step_url; $("#step").classList.remove("disabled");
  ["#compliance","#png","#svg"].forEach(id=>$(id).disabled=false); state.zoom=1; applyZoom(); setTab("model");
}
function applyZoom(){ const svg=$("#canvas svg"); if(svg) svg.style.transform=`scale(${state.zoom})`; $("#zoom-label").textContent=`${Math.round(state.zoom*100)}%`; }
function download(blob,name){ const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
async function generate() {
  const description=$("#description").value.trim();
  if(description.length<2){toast("请先输入技术描述");$("#description").focus();return;}
  const button=$("#generate");button.disabled=true;button.innerHTML='<span class="spinner"></span>';
  const progress=$("#generation-progress"), stages=[[12,"正在解析结构参数","识别零件类型、尺寸与工程约束…"],[38,"正在生成二维附图","构建轮廓、中心线和尺寸标注…"],[68,"正在构建 3D 几何","生成参数化实体与可视化网格…"],[88,"正在封装 STEP","写入 ISO 10303 交换格式…"]];
  progress.classList.add("show");let stage=0;const update=()=>{const [value,title,detail]=stages[stage];$("#progress-bar").style.width=`${value}%`;$("#progress-percent").textContent=`${value}%`;$("#progress-title").textContent=title;$("#progress-detail").textContent=detail;stage=Math.min(stage+1,stages.length-1)};update();const timer=setInterval(update,650);
  $("#canvas").classList.remove("empty");$("#canvas").innerHTML='<div class="spinner"></div>';
  try {
    const response=await fetch("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description,part_type:state.part,field:$("#field").value,use_ai:$("#use-ai").checked})});
    if(!response.ok) throw new Error(`生成失败 (${response.status})`);
    const result=await response.json();clearInterval(timer);$("#progress-bar").style.width="100%";$("#progress-percent").textContent="100%";$("#progress-title").textContent="生成完成";$("#progress-detail").textContent="3D 模型与 STEP 文件已就绪";await new Promise(r=>setTimeout(r,350));result.time=new Date().toLocaleString("zh-CN",{hour12:false});
    state.history.unshift(result);state.history=state.history.slice(0,12);localStorage.setItem("cad-history",JSON.stringify(state.history));renderHistory();showResult(result);toast(`${labels[state.part]}附图已生成`);
  } catch(error) { $("#canvas").classList.add("empty");$("#canvas").innerHTML=`<div class="placeholder"><p>${error.message}</p><small>请检查后端服务后重试</small></div>`;toast(error.message); }
  finally {clearInterval(timer);progress.classList.remove("show");button.disabled=false;button.innerHTML="<span>⌁</span> 生成附图";}
}

$("#description").oninput=e=>$("#counter").textContent=`${e.target.value.length}/5000`;
$("#example").onclick=()=>{const list=examples[state.part],index=state.exampleIndex[state.part]||0;$("#description").value=list[index];state.exampleIndex[state.part]=(index+1)%list.length;$("#description").dispatchEvent(new Event("input"));};
$("#clear").onclick=()=>{$("#description").value="";$("#description").dispatchEvent(new Event("input"));};
$("#parts").onclick=e=>{const button=e.target.closest("button");if(!button)return;state.part=button.dataset.part;$$(".parts button").forEach(b=>b.classList.toggle("active",b===button));};
$("#document").onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>2*1024*1024){toast("文件不能超过 2MB");return;}$("#description").value=await file.text();$("#description").dispatchEvent(new Event("input"));toast("文档已导入");};
$("#generate").onclick=generate;
$$(".tabs button").forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
$("#zoom-in").onclick=()=>{state.zoom=Math.min(1.8,state.zoom+.1);applyZoom();};
$("#zoom-out").onclick=()=>{state.zoom=Math.max(.5,state.zoom-.1);applyZoom();};
$("#reset").onclick=()=>{state.zoom=1;applyZoom();};
$("#compliance").onclick=()=>{setTab("params");toast(state.result.compliance.every(c=>c.passed)?"全部合规检查通过":"存在未通过项目");};
$("#svg").onclick=()=>download(new Blob([state.result.svg],{type:"image/svg+xml"}),`${state.result.part_type}-${state.result.id.slice(0,8)}.svg`);
$("#png").onclick=()=>{const image=new Image();const blob=new Blob([state.result.svg],{type:"image/svg+xml"});const url=URL.createObjectURL(blob);image.onload=()=>{const canvas=document.createElement("canvas");canvas.width=1800;canvas.height=1240;canvas.getContext("2d").drawImage(image,0,0,1800,1240);canvas.toBlob(png=>download(png,`${state.result.part_type}-${state.result.id.slice(0,8)}.png`));URL.revokeObjectURL(url);};image.src=url;};
$("#clear-history").onclick=()=>{state.history=[];localStorage.removeItem("cad-history");renderHistory();toast("历史记录已清空");};
renderHistory();
