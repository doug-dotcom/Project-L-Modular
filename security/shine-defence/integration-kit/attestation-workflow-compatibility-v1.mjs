#!/usr/bin/env node
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

export const SHINE_DEFENCE_ATTESTATION_WORKFLOW_COMPATIBILITY_VERSION='1.1.0';

const root=fileURLToPath(new URL('../../../',import.meta.url));
const contractPath=root+'security/shine-defence/attestation-workflow-compatibility-v1.json';
const lineSet=source=>source.split(/\r?\n/).map(line=>line.trim());
const occurrences=(source,needle)=>source.split(needle).length-1;

export function assessAttestationWorkflow({source,contract}){
  if(typeof source!=='string'||!source.trim()) throw new Error('workflow source required');
  if(!contract||contract.contract!=='shine-defence/attestation-workflow-compatibility-v1'||contract.version!=='1.1.0'){
    throw new Error('unsupported attestation compatibility contract');
  }

  const lines=lineSet(source);
  const violations=[];
  const required=contract.required;
  const bounded=contract.boundedExceptions;

  if(!lines.includes('contents: '+required.permissions.contents)) violations.push('contents-permission');
  if(!lines.includes('id-token: '+required.permissions['id-token'])) violations.push('oidc-permission');
  const writeLines=lines.filter(line=>/^[A-Za-z0-9_-]+\s*:\s*write\s*(?:#.*)?$/.test(line));
  if(writeLines.some(line=>line!=='id-token: write')) violations.push('broader-write-permission');

  if(!source.includes('\n  schedule:\n')) violations.push('schedule-trigger');
  if(!source.includes('\n  workflow_dispatch:\n')) violations.push('workflow-dispatch-trigger');
  for(const trigger of required.forbiddenTriggers){
    if(source.includes('\n  '+trigger+':')) violations.push('forbidden-trigger:'+trigger);
  }

  if(!lines.includes('runs-on: '+required.runner)) violations.push('runner-pin');
  if(!lines.includes('shell: '+required.strictShell)) violations.push('strict-shell');

  const sourceBranchLine=lines.find(line=>line.startsWith('SHINE_DEFENCE_SOURCE_BRANCH: '));
  const sourceBranch=sourceBranchLine?sourceBranchLine.slice('SHINE_DEFENCE_SOURCE_BRANCH: '.length).trim():'';
  const sourceBranchPattern=new RegExp(required.sourceBranch.pattern);
  if(!sourceBranch||!sourceBranchPattern.test(sourceBranch)||sourceBranch.includes('..')) violations.push('source-branch-binding');
  if(!lines.some(line=>line.startsWith('SHINE_DEFENCE_TARGET_ID: ')&&line.length>'SHINE_DEFENCE_TARGET_ID: '.length)) violations.push('target-binding');

  if(source.includes('secrets.')) violations.push('secret-context-reference');
  const tokenRefs=occurrences(source,'${{ github.token }}');
  const tokenEnv=lines.filter(line=>line==='GITHUB_TOKEN: ${{ github.token }}').length;
  if(tokenRefs<1||tokenEnv<1||tokenRefs!==tokenEnv) violations.push('github-token-binding');
  if(/persist-credentials\s*:\s*true/i.test(source)) violations.push('credential-persistence');

  const audiences=[...source.matchAll(/audience=([A-Za-z0-9._:-]+)/g)].map(match=>match[1]);
  if(!audiences.length||audiences.some(value=>!value.startsWith(bounded.oidc.audiencePrefix))) violations.push('oidc-audience');

  return {
    ok:violations.length===0,
    role:contract.role,
    version:contract.version,
    sourceBranch,
    deploymentBranchVerificationRequired:required.sourceBranch.mustMatchDeploymentSource===true,
    keyContinuity:bounded.oidc.keyContinuity,
    tokenReferences:tokenRefs,
    oidcAudiences:[...new Set(audiences)].sort(),
    violations
  };
}

function selfTest(){
  const contract=JSON.parse(readFileSync(contractPath,'utf8'));
  const good=[
    'name: Shine Defence Release Head',
    'on:',
    '  schedule:',
    "    - cron: '*/5 * * * *'",
    '  workflow_dispatch:',
    '  push:',
    '    branches: [main]',
    'permissions:',
    '  contents: read',
    '  id-token: write',
    'defaults:',
    '  run:',
    '    shell: bash --noprofile --norc -euo pipefail {0}',
    'jobs:',
    '  attest:',
    '    runs-on: ubuntu-24.04',
    '    env:',
    '      SHINE_DEFENCE_TARGET_ID: railway:example',
    '      SHINE_DEFENCE_SOURCE_BRANCH: build/layer-001-foundation',
    '    steps:',
    '      - run: echo "audience=shine-defence-release-head"',
    '        env:',
    '          GITHUB_TOKEN: ${{ github.token }}',
    ''
  ].join('\n');
  const pass=assessAttestationWorkflow({source:good,contract});
  if(!pass.ok||pass.sourceBranch!=='build/layer-001-foundation') throw new Error('valid attestation workflow rejected: '+pass.violations.join(','));

  const bad=good.replace('contents: read','contents: write').replace('audience=shine-defence-release-head','audience=other').replace('build/layer-001-foundation','../unsafe');
  const fail=assessAttestationWorkflow({source:bad,contract});
  if(fail.ok||!fail.violations.includes('broader-write-permission')||!fail.violations.includes('oidc-audience')||!fail.violations.includes('source-branch-binding')){
    throw new Error('unsafe attestation workflow accepted');
  }
  console.log('SHINE DEFENCE ATTESTATION WORKFLOW COMPATIBILITY: PASS');
}

const isDirect=Boolean(process.argv[1])&&fileURLToPath(import.meta.url)===process.argv[1];
if(isDirect){
  const args=process.argv.slice(2);
  if(args.includes('--self-test')){
    selfTest();
  }else{
    const contract=JSON.parse(readFileSync(contractPath,'utf8'));
    const i=args.indexOf('--workflow');
    if(i<0||!args[i+1]){
      console.error('Usage: attestation-workflow-compatibility-v1.mjs --workflow <path> | --self-test');
      process.exit(64);
    }
    const report=assessAttestationWorkflow({source:readFileSync(args[i+1],'utf8'),contract});
    console.log(JSON.stringify(report,null,2));
    if(!report.ok) process.exitCode=1;
  }
}
