#!/usr/bin/env node
/**
 * render_report.mjs —— 共用 Word 渲染器（docx-js）
 * 用法：node render_report.mjs <model.json> <out.docx>
 * 输入 model.json 由 build_report_docx.py 解析报告 Markdown 生成（块模型）。
 * 负责：单页垂直居中封面、链接转脚注、图表占位插图、目录、页眉页脚页码、设计系统。
 */
import fs from "fs";
import {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, PageBreak, TableOfContents, FootnoteReferenceRun,
  ExternalHyperlink, LevelFormat, SectionType, TableLayoutType
} from "docx";

const [,, modelPath, outPath] = process.argv;
const M = JSON.parse(fs.readFileSync(modelPath, "utf-8"));

const NAVY="1F3864", RED="9B1B30", GRAY="595959", LINE="C9C9C9";
const BODY="宋体", HEAD="黑体", LAT="Times New Roman";

// 字体规范：西文一律 Times New Roman，中文用指定东亚字体（宋体/黑体）
const FT = (cn) => ({ascii:LAT, hAnsi:LAT, eastAsia:cn||BODY});
const trun = (t,o={}) => new TextRun({text:t, font:FT(o.font), size:o.size||24,
  bold:!!o.b, italics:!!o.i, color:o.color, superScript:!!o.sup});

// 把模型 runs 渲染为 docx runs（含脚注引用）
function runs(arr){
  const out=[];
  for(const r of (arr||[])){
    if(r.t) out.push(trun(r.t,{b:r.b,color:r.color}));
    if(r.fn) out.push(new FootnoteReferenceRun(r.fn));
  }
  return out.length?out:[trun("")];
}

function para(block){
  return new Paragraph({spacing:{line:360, after:80}, indent:{firstLine:480},
    alignment:AlignmentType.JUSTIFIED, children:runs(block.runs)});
}
function lead(block){
  return new Paragraph({spacing:{line:360, after:80}, indent:{firstLine:480},
    alignment:AlignmentType.JUSTIFIED,
    children:[trun(block.label,{b:true,color:NAVY}), ...runs(block.runs)]});
}
function bullet(block){
  return new Paragraph({numbering:{reference:"kf",level:0}, spacing:{line:340,after:60},
    children:runs(block.runs)});
}
function heading(block){
  const sizes={1:32,2:28,3:26};
  const hl={1:HeadingLevel.HEADING_1,2:HeadingLevel.HEADING_2,3:HeadingLevel.HEADING_3}[block.level];
  const p={spacing:{before:240, after:120}};
  if(block.level===1) p.border={bottom:{style:BorderStyle.SINGLE,size:6,color:NAVY,space:4}};
  return new Paragraph({heading:hl, ...p,
    children:[new TextRun({text:block.text, font:FT(HEAD), size:sizes[block.level], bold:true, color:"000000"})]});
}
function image(block){
  return [
    new Paragraph({alignment:AlignmentType.CENTER, spacing:{before:120},
      children:[new ImageRun({type:"png", data:fs.readFileSync(block.path),
        transformation:{width:block.w||540, height:block.h||340},
        altText:{title:block.caption||"", description:block.caption||"", name:"chart"}})]}),
    new Paragraph({alignment:AlignmentType.CENTER, spacing:{before:40,after:160},
      children:[new TextRun({text:block.caption||"", font:FT(BODY), size:18, color:GRAY})]})
  ];
}
// 单元格内容：支持纯字符串（向后兼容）或行内 runs（含 [文字](链接) 转脚注、**加粗**）
function cellChildren(cell, head){
  const arr = Array.isArray(cell) ? cell : [{t:String(cell)}];
  const out=[];
  for(const r of arr){
    if(r.t!==undefined && r.t!=="")
      out.push(new TextRun({text:String(r.t), font:FT(BODY), size:head?18:17,
        bold: head|| !!r.b, color: head?"FFFFFF":(r.color||"222222")}));
    if(r.fn!==undefined) out.push(new FootnoteReferenceRun(r.fn));
  }
  return out.length?out:[new TextRun({text:"", font:FT(BODY), size:head?18:17})];
}
function table(block){
  const widths=block.widths;
  const mk=(cell,ci,head,band)=> new TableCell({width:{size:widths[ci],type:WidthType.DXA},
    margins:{top:70,bottom:70,left:110,right:110},
    shading: head?{fill:NAVY,type:ShadingType.CLEAR}:(band?{fill:"EEF1F6",type:ShadingType.CLEAR}:undefined),
    borders:{top:{style:BorderStyle.SINGLE,size:2,color:LINE},bottom:{style:BorderStyle.SINGLE,size:2,color:LINE},
             left:{style:BorderStyle.SINGLE,size:2,color:LINE},right:{style:BorderStyle.SINGLE,size:2,color:LINE}},
    children:[new Paragraph({alignment: ci===0?AlignmentType.CENTER:AlignmentType.LEFT, spacing:{line:240},
      children: cellChildren(cell, head)})]});
  const rows=[ new TableRow({tableHeader:true, children:block.header.map((h,ci)=>mk(h,ci,true,false))}) ];
  block.rows.forEach((r,ri)=> rows.push(new TableRow({children:r.map((c,ci)=>mk(c,ci,false,ri%2===0))})));
  return new Table({width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},
    columnWidths:widths, layout:TableLayoutType.FIXED, rows});
}

// ---- 正文块 ----
const main=[];
for(const b of M.blocks){
  if(b.type==="toc"){
    main.push(new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:160},
      children:[new TextRun({text:"目　录", font:FT(HEAD), size:32, bold:true})]}));
    main.push(new TableOfContents("TOC",{hyperlink:true, headingStyleRange:"1-2"}));
  } else if(b.type==="pagebreak"){ main.push(new Paragraph({children:[new PageBreak()]})); }
  else if(b.type==="h"){ main.push(heading(b)); }
  else if(b.type==="lead"){ main.push(lead(b)); }
  else if(b.type==="bullet"){ main.push(bullet(b)); }
  else if(b.type==="image"){ main.push(...image(b)); }
  else if(b.type==="table"){ main.push(table(b)); }
  else { main.push(para(b)); }
}

// ---- 脚注 ----
const footnotes={};
for(const [id,obj] of Object.entries(M.footnotes||{})){
  const children=[];
  if(obj.url){
    children.push(new TextRun({text:(obj.text||"")+"　北大法宝：", font:FT(BODY), size:18}));
    children.push(new ExternalHyperlink({link:obj.url,
      children:[new TextRun({text:obj.url, font:LAT, size:18, color:"1F4E79", underline:{}})]}));
  } else {
    children.push(new TextRun({text:obj.text||"", font:FT(BODY), size:18}));
  }
  footnotes[id]={children:[new Paragraph({spacing:{line:240}, children})]};
}

// ---- 封面 ----
const cov=M.cover||{};
const titleLines = (cov.titleLines && cov.titleLines.length) ? cov.titleLines : [cov.title||""];
const coverChildren=[
  new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:120},
    border:{bottom:{style:BorderStyle.SINGLE,size:8,color:NAVY,space:6}},
    children:[new TextRun({text:cov.kindTop||"关　于", font:FT(HEAD), size:44, bold:true, color:NAVY})]}),
];
titleLines.forEach((line,i)=>coverChildren.push(
  new Paragraph({alignment:AlignmentType.CENTER,
    spacing:{before:i===0?240:80, after:i===titleLines.length-1?120:80},
    children:[new TextRun({text:line, font:FT(HEAD), size:52, bold:true, color:"1F1F1F"})]})));
if(cov.subtitle) coverChildren.push(new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:120},
  children:[new TextRun({text:cov.subtitle, font:FT(HEAD), size:28, color:GRAY})]}));
coverChildren.push(new Paragraph({alignment:AlignmentType.CENTER, spacing:{before:120,after:120},
  border:{top:{style:BorderStyle.SINGLE,size:8,color:NAVY,space:6}},
  children:[new TextRun({text:cov.kind||"分析报告", font:FT(HEAD), size:40, bold:true, color:NAVY})]}));
// 署名块放封面页脚：天然贴页底且不会溢出本页
const coverFooter=new Footer({children:(cov.meta||[]).map(line=>
  new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:60},
    children:[new TextRun({text:line, font:FT(BODY), size:21, color:"333333"})]}))});

const PAGE={size:{width:11906,height:16838}, margin:{top:1440,bottom:1440,left:1800,right:1800}};
const headerSimple=new Header({children:[new Paragraph({alignment:AlignmentType.RIGHT,
  border:{bottom:{style:BorderStyle.SINGLE,size:4,color:LINE,space:2}},
  children:[new TextRun({text:cov.runningTitle||cov.title||"", font:FT(BODY), size:16, color:GRAY})]})]});
const footerPage=new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,
  children:[ new TextRun({text:"第 ",font:FT(BODY),size:18,color:GRAY}),
    new TextRun({children:[PageNumber.CURRENT],font:FT(BODY),size:18,color:GRAY}),
    new TextRun({text:" 页 / 共 ",font:FT(BODY),size:18,color:GRAY}),
    new TextRun({children:[PageNumber.TOTAL_PAGES],font:FT(BODY),size:18,color:GRAY}),
    new TextRun({text:" 页",font:FT(BODY),size:18,color:GRAY}) ]})]});

const doc=new Document({
  styles:{ default:{document:{run:{font:FT(BODY),size:24}}},
    paragraphStyles:[1,2,3].map(l=>({
      id:`Heading${l}`, name:`Heading ${l}`, basedOn:"Normal", next:"Normal", quickFormat:true,
      run:{size:{1:32,2:28,3:26}[l], bold:true, font:FT(HEAD)},
      paragraph:{spacing:{before:240,after:120}, outlineLevel:l-1}}))},
  numbering:{config:[{reference:"kf", levels:[{level:0, format:LevelFormat.BULLET, text:"▪",
    alignment:AlignmentType.LEFT, style:{run:{color:NAVY}, paragraph:{indent:{left:560,hanging:280}}}}]}]},
  footnotes,
  sections:[
    { properties:{ type:SectionType.NEXT_PAGE, verticalAlign:VerticalAlign.CENTER, page:PAGE },
      footers:{default:coverFooter}, children:coverChildren },
    { properties:{ type:SectionType.NEXT_PAGE, page:PAGE },
      headers:{default:headerSimple}, footers:{default:footerPage}, children:main }
  ]
});

Packer.toBuffer(doc).then(b=>{ fs.writeFileSync(outPath, b); console.log("docx ->", outPath); });
