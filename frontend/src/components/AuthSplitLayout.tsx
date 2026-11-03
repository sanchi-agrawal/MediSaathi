import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './ui'
import { LanguageToggle } from './LanguageToggle'
import { useLanguage } from '../lib/language'
import healthcareImage from '../assets/auth-healthcare.png'
import '../demo-login.css'

export default function AuthSplitLayout({children}:{children:ReactNode}){
  useUiLanguage()

  const {language}=useLanguage()
  return <main className="auth-page image-auth demo-login" id="main-content" lang={language}>
    <div className="auth-image-panel">
      <img src={healthcareImage} alt="" decoding="async"/>
      <div className="auth-image-copy">
        <h1 className="auth-image-heading"><span>{language==='hi'?"अपनी सेहत को":tr("A clearer way to")}</span>{" "}<span className="auth-image-highlight">{language==='hi'?"बेहतर समझें।":tr("manage care.")}</span></h1>
        <span className="auth-image-accent" aria-hidden="true"/>
        <p className="auth-image-description">{language==='hi'?<>पर्चे, दवाइयों और अगले कदमों को<br/>आसानी और भरोसे के साथ समझें।</>:<>{tr("Understand prescriptions,")}<br/>{tr("medicines and next steps")}<br/>{tr("with confidence.")}</>}</p>
      </div>
    </div>
    <section className="auth-form-side" aria-label={language==='hi'?"प्रवेश फ़ॉर्म":tr("Access form")}>
      <header className="demo-login-header">
        <div className="demo-login-header-row"><Brand/><LanguageToggle/></div>
        <Link className="auth-back-home" to="/">{language==='hi'?"मुख्य पृष्ठ":tr("Back to home")}</Link>
      </header>
      <div className="demo-login-form-wrap">{children}</div>
    </section>
  </main>
}
