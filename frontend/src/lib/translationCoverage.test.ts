import { expect,it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { hindi } from './language'

function files(dir:string):string[]{return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)])}
it('has Hindi entries for every literal UI translation key and medicine/instruction field label',()=>{
  const missing:string[]=[]
  for(const file of files(path.resolve('src')).filter(f=>f.endsWith('.tsx')&&!f.includes('.test.'))){
    const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
    function check(key:string){if(!Object.hasOwn(hindi,key.trim()))missing.push(path.basename(file)+': '+key)}
    function visit(n:ts.Node){
      if(ts.isCallExpression(n)&&['tr','t'].includes(n.expression.getText(ast))&&n.arguments[0]&&ts.isStringLiteral(n.arguments[0]))check(n.arguments[0].text)
      if(ts.isVariableDeclaration(n)&&n.name.getText(ast)==='labels'&&n.initializer&&ts.isObjectLiteralExpression(n.initializer)){
        for(const p of n.initializer.properties)if(ts.isPropertyAssignment(p)&&ts.isStringLiteral(p.initializer))check(p.initializer.text)
      }
      ts.forEachChild(n,visit)
    }
    visit(ast)
  }
  expect(missing).toEqual([])
})
it('does not leave hardcoded English JSX text outside intentional names and language choices',()=>{
  const allowed=new Set(['Medi','Saathi','MediSaathi','English','Hinglish','ENGLISH · हिन्दी · HINGLISH'])
  const untranslated:string[]=[]
  for(const file of files(path.resolve('src')).filter(f=>f.endsWith('.tsx')&&!f.includes('.test.'))){
    const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
    function visit(n:ts.Node){if(ts.isJsxText(n)&&/[A-Za-z]/.test(n.text)&&!allowed.has(n.text.trim()))untranslated.push(path.basename(file)+': '+n.text.trim());ts.forEachChild(n,visit)}visit(ast)
  }
  expect(untranslated).toEqual([])
})
it('does not leave untranslated literal descriptions, placeholders or accessibility labels',()=>{
  const names=new Set(['aria-label','alt','title','placeholder','eyebrow','description','label'])
  const untranslated:string[]=[]
  for(const file of files(path.resolve('src')).filter(f=>f.endsWith('.tsx')&&!f.includes('.test.'))){
    const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
    function visit(n:ts.Node){
      if(ts.isJsxAttribute(n)&&names.has(n.name.getText(ast))&&n.initializer&&ts.isStringLiteral(n.initializer)&&/[A-Za-z]/.test(n.initializer.text)&&n.initializer.text!=='MediSaathi')untranslated.push(path.basename(file)+': '+n.initializer.text)
      ts.forEachChild(n,visit)
    }
    visit(ast)
  }
  expect(untranslated).toEqual([])
})
