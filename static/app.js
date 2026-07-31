import { CadModelViewer } from "/static/model-viewer.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { part: "bearing", result: null, zoom: 1, exampleIndex: {}, history: JSON.parse(localStorage.getItem("cad-history") || "[]") };
const useCases = ["高速电机转子","矿山输送机","食品包装设备","海上风电机组","数控机床主轴","农业灌溉泵","化工反应釜","仓储机器人","船舶推进系统","轨道交通设备","光伏跟踪支架","医疗检测仪器","航空地面设备","冶金轧制产线","半导体搬运模组","污水处理装置","印刷机械","注塑机","实验室试验台","自动化装配线"];
const examples = {
  bearing: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["深沟球","圆柱滚子","角接触球","调心滚子","推力球"][i%5]}轴承，外径${62+i*8}mm，内径${24+i*4}mm，宽度${14+i}mm，包含${8+(i%5)*2}个滚动体，用于${useCases[i]}。`),
  flange: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["平焊","高压对焊","真空","设备连接","带颈"][i%5]}法兰，外径${110+i*12}mm，内径${42+i*6}mm，厚度${12+i*2}mm，均布${[4,6,8,10,12][i%5]}个螺栓孔，用于${useCases[i]}。`),
  valve: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["截止阀","闸阀","调节阀","蝶阀","止回阀"][i%5]}，公称直径${32+i*6}mm，阀体长度${120+i*11}mm，总高度${160+i*13}mm，双端法兰连接，应用于${useCases[i]}。`),
  shaft: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["阶梯轴","输入轴","输出轴","空心传动轴","支承轴"][i%5]}，总长${160+i*24}mm，最大直径${38+i*5}mm，包含${3+i%4}段轴肩，键槽宽${8+i%7}mm，用于${useCases[i]}。`),
  gear: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["直齿圆柱齿轮","精密小齿轮","重载传动齿轮","减速机齿轮","仪表齿轮"][i%5]}，模数${[1.5,2,2.5,3,4][i%5]}，齿数${16+i*2}，中心孔${12+i*3}mm，齿宽${10+i*2}mm，用于${useCases[i]}。`),
  screw: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["精密滚珠丝杠","梯形传动丝杠","重载升降丝杠","定位丝杠","微型执行器丝杠"][i%5]}，长度${160+i*32}mm，直径${16+i*2}mm，导程${[4,5,8,10,12][i%5]}mm，${i%3===0?"双头":"单头"}结构，用于${useCases[i]}。`),
  coupling: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["法兰联轴器","刚性联轴器","弹性法兰联轴器","重载联轴器","伺服联轴器"][i%5]}，外径${58+i*7}mm，总长${70+i*8}mm，轴孔${16+i*3}mm，配置${[4,6,8,10][i%4]}个连接螺栓，用于${useCases[i]}。`),
  seal: Array.from({length:20},(_,i)=>`${["生成","设计","构造","绘制"][i%4]}${["双唇油封","单唇旋转密封件","耐压轴端密封件","防尘密封件","耐高温密封件"][i%5]}，外径${42+i*7}mm，内径${22+i*5}mm，宽度${7+i%10}mm，${i%3===0?"双唇":"单唇"}结构，用于${useCases[i]}。`)
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
