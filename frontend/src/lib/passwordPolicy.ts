// Prototype-only compromise. Do not deploy with real patient data.
export const MIN_PASSWORD_LENGTH=6
export const MAX_PASSWORD_LENGTH=128
export function validNewPassword(password:string){return password.length>=MIN_PASSWORD_LENGTH&&password.length<=MAX_PASSWORD_LENGTH}
