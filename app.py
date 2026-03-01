// ─────────────────────────────────────────────────────────────
// ZIAOT — CLOUDFLARE WORKER
// Maneja: Stripe success, validación, consumo y reenvío de tokens
// KV: TOKENS_KV
// ─────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── CORS: permite solicitudes desde Streamlit ──
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    // Pre-flight CORS
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // ── Routing ──
    if (url.pathname === "/success-single") {
      return await handleSuccess(request, env, "single");
    }

    if (url.pathname === "/success-sub") {
      return await handleSuccess(request, env, "sub");
    }

    if (url.pathname === "/validate-token") {
      return await handleValidate(url, env, corsHeaders);
    }

    if (url.pathname === "/consume-token" && request.method === "POST") {
      return await handleConsume(request, env, corsHeaders);
    }

    if (url.pathname === "/resend-token" && request.method === "POST") {
      return await handleResend(request, env, corsHeaders);
    }

    return new Response("Not Found", { status: 404 });
  },
};

// ─────────────────────────────────────────────────────────────
// STRIPE SUCCESS — Verifica pago, crea token, envía email
// ─────────────────────────────────────────────────────────────
async function handleSuccess(request, env, type) {
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");

  if (!sessionId) return new Response("Missing session_id", { status: 400 });

  // Idempotencia: si ya se procesó esta sesión, no crear token duplicado
  const existingSession = await env.TOKENS_KV.get(`session:${sessionId}`);
  if (existingSession) {
    // Redirige al token ya creado si existe
    const existingToken = existingSession !== "used" ? existingSession : null;
    if (existingToken) {
      return Response.redirect(`${env.STREAMLIT_URL}?token=${existingToken}`, 302);
    }
    return new Response("Session already processed", { status: 400 });
  }

  // Verificar pago con Stripe
  const stripeRes = await fetch(
    `https://api.stripe.com/v1/checkout/sessions/${sessionId}`,
    {
      headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
    }
  );

  const session = await stripeRes.json();
  const email = session?.customer_details?.email;

  if (!email || session.payment_status !== "paid") {
    return new Response("Invalid or unpaid session", { status: 400 });
  }

  // Crear token
  const token = crypto.randomUUID();
  const now = Date.now();

  let record;

  if (type === "single") {
    record = {
      type: "single",
      status: "active",
      email: email,
      used: false,
      created: now,
      expires_at: now + 6 * 30 * 24 * 60 * 60 * 1000, // 6 meses
    };
  } else {
    record = {
      type: "sub",
      status: "active",
      email: email,
      uses_left: 100,
      created: now,
      expires_at: now + 30 * 24 * 60 * 60 * 1000, // 30 días
    };
  }

  // Guardar token y lookup por email
  await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));
  await env.TOKENS_KV.put(`email:${email.toLowerCase()}`, token);

  // Marcar sesión como procesada (guardamos el token para idempotencia)
  await env.TOKENS_KV.put(`session:${sessionId}`, token);

  // Enviar email de bienvenida
  await sendAccessEmail(env, email, token, type, record.expires_at, record.uses_left ?? null);

  // Redirigir a Streamlit con el token
  return Response.redirect(`${env.STREAMLIT_URL}?token=${token}`, 302);
}

// ─────────────────────────────────────────────────────────────
// VALIDATE TOKEN
// ─────────────────────────────────────────────────────────────
async function handleValidate(url, env, corsHeaders) {
  const token = url.searchParams.get("token");

  if (!token) return json({ valid: false, reason: "no_token" }, corsHeaders);

  const data = await env.TOKENS_KV.get(`token:${token}`);
  if (!data) return json({ valid: false, reason: "not_found" }, corsHeaders);

  const record = JSON.parse(data);
  const now = Date.now();

  // Token expirado por tiempo
  if (now > record.expires_at) {
    if (record.status === "active") {
      record.status = "expired";
      await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));
    }
    return json({ valid: false, reason: "expired", type: record.type }, corsHeaders);
  }

  // Token de un solo uso ya consumido
  if (record.type === "single" && record.used) {
    return json({ valid: false, reason: "consumed", type: record.type }, corsHeaders);
  }

  // Token sub sin usos
  if (record.type === "sub" && record.uses_left <= 0) {
    if (record.status === "active") {
      record.status = "consumed";
      await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));
    }
    return json({ valid: false, reason: "consumed", type: record.type }, corsHeaders);
  }

  // Token inactivo por otra razón
  if (record.status !== "active") {
    return json({ valid: false, reason: record.status, type: record.type }, corsHeaders);
  }

  // is_new: true si el token fue creado hace menos de 2 minutos
  // Streamlit lo usa para mostrar el toast de bienvenida post-pago
  const isNew = (Date.now() - record.created) < 2 * 60 * 1000;

  return json(
    {
      valid: true,
      type: record.type,
      uses_left: record.uses_left ?? null,
      expires_at: record.expires_at,
      is_new: isNew,
    },
    corsHeaders
  );
}

// ─────────────────────────────────────────────────────────────
// CONSUME TOKEN
// ─────────────────────────────────────────────────────────────
async function handleConsume(request, env, corsHeaders) {
  const body = await request.json();
  const token = body?.token;

  if (!token) return json({ success: false, reason: "no_token" }, corsHeaders);

  const data = await env.TOKENS_KV.get(`token:${token}`);
  if (!data) return json({ success: false, reason: "not_found" }, corsHeaders);

  const record = JSON.parse(data);
  const now = Date.now();

  if (record.status !== "active") {
    return json({ success: false, reason: record.status }, corsHeaders);
  }

  if (now > record.expires_at) {
    record.status = "expired";
    await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));
    return json({ success: false, reason: "expired" }, corsHeaders);
  }

  if (record.type === "single") {
    if (record.used) return json({ success: false, reason: "consumed" }, corsHeaders);

    record.used = true;
    record.status = "consumed";
    await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));

    return json({ success: true, type: "single", uses_left: null }, corsHeaders);
  }

  if (record.type === "sub") {
    if (record.uses_left <= 0) {
      record.status = "consumed";
      await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));
      return json({ success: false, reason: "consumed" }, corsHeaders);
    }

    record.uses_left -= 1;
    if (record.uses_left <= 0) record.status = "consumed";

    await env.TOKENS_KV.put(`token:${token}`, JSON.stringify(record));

    return json(
      {
        success: true,
        type: "sub",
        uses_left: record.uses_left,
        expires_at: record.expires_at,
      },
      corsHeaders
    );
  }

  return json({ success: false, reason: "unknown_type" }, corsHeaders);
}

// ─────────────────────────────────────────────────────────────
// RESEND TOKEN — No confirma si el email existe (seguridad)
// Rate limit: 5 requests/min por IP — usando KV como contador
// ─────────────────────────────────────────────────────────────
async function handleResend(request, env, corsHeaders) {
  const body = await request.json();
  const email = body?.email?.toLowerCase()?.trim();

  // Siempre respondemos lo mismo para no revelar si el email existe o fue bloqueado
  const genericResponse = json(
    { sent: true, message: "If this email has an active purchase, you will receive access shortly." },
    corsHeaders
  );

  // ── Rate limiting por IP ──
  // Clave: rl:{ip} → contador de requests en la ventana de 1 minuto
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const rlKey = `rl:resend:${ip}`;
  const rlWindow = 60; // segundos
  const rlMax = 5;     // máximo requests por ventana

  const rlData = await env.TOKENS_KV.get(rlKey);
  const rlCount = rlData ? parseInt(rlData) : 0;

  if (rlCount >= rlMax) {
    // Bloqueado — respuesta genérica para no revelar el bloqueo
    return genericResponse;
  }

  // Incrementar contador; TTL = 60s para que expire automáticamente
  await env.TOKENS_KV.put(rlKey, String(rlCount + 1), { expirationTtl: rlWindow });

  if (!email) return genericResponse;

  const token = await env.TOKENS_KV.get(`email:${email}`);
  if (!token) return genericResponse;

  const data = await env.TOKENS_KV.get(`token:${token}`);
  if (!data) return genericResponse;

  const record = JSON.parse(data);

  // Enviamos el mail con el mismo template de bienvenida
  await sendAccessEmail(env, email, token, record.type, record.expires_at, record.uses_left ?? null);

  return genericResponse;
}

// ─────────────────────────────────────────────────────────────
// EMAIL — Template HTML bilingüe diferenciado por plan
// ─────────────────────────────────────────────────────────────
async function sendAccessEmail(env, email, token, type, expiresAt, usesLeft) {
  const accessUrl = `${env.STREAMLIT_URL}?token=${token}`;
  const expireDate = new Date(expiresAt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const expireDateEs = new Date(expiresAt).toLocaleDateString("es-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const isSingle = type === "single";

  // ── Contenido diferenciado por plan ──
  const planNameEn = isSingle ? "Pay per use" : "Monthly 100 uses";
  const planNameEs = isSingle ? "Pago por uso" : "100 usos mensuales";

  const planDetailsEn = isSingle
    ? `<li>✅ <strong>1 use total</strong> — your token is consumed after one successful calculation</li>
       <li>⏳ Access expires on <strong>${expireDate}</strong> (6 months) or when used, whichever comes first</li>
       <li>🔒 Single-use — cannot be reused after the calculation is completed</li>`
    : `<li>✅ <strong>${usesLeft} uses remaining</strong> out of 100</li>
       <li>⏳ Access valid until <strong>${expireDate}</strong> (30 days from purchase)</li>
       <li>🔄 Renew monthly by purchasing a new subscription</li>
       <li>🔒 After 100 uses or expiration date, whichever comes first, access will be disabled</li>`;

  const planDetailsEs = isSingle
    ? `<li>✅ <strong>1 uso total</strong> — tu token se consume luego de un cálculo exitoso</li>
       <li>⏳ Acceso válido hasta el <strong>${expireDateEs}</strong> (6 meses) o hasta que se use, lo que ocurra primero</li>
       <li>🔒 Uso único — no se puede reutilizar después de completar el cálculo</li>`
    : `<li>✅ <strong>${usesLeft} usos restantes</strong> de 100</li>
       <li>⏳ Acceso válido hasta el <strong>${expireDateEs}</strong> (30 días desde la compra)</li>
       <li>🔄 Renueva mensualmente volviendo a comprar la suscripción</li>
       <li>🔒 Al alcanzar 100 usos o la fecha de vencimiento (lo que ocurra primero), el acceso se deshabilitará</li>`;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ZaiOT — Access</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:linear-gradient(135deg,#1f6fd2,#7b61ff);padding:36px 40px;text-align:center;">
            <h1 style="margin:0;color:#fff;font-size:36px;font-weight:800;letter-spacing:2px;">ZaiOT</h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:13px;letter-spacing:1px;">OVERTIME DEDUCTION CALCULATOR</p>
          </td>
        </tr>

        <!-- ENGLISH SECTION -->
        <tr>
          <td style="padding:36px 40px 24px;">
            <p style="font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px;margin:0 0 4px;">🇺🇸 English</p>
            <h2 style="margin:0 0 12px;color:#1a1a2e;font-size:22px;">Your access is ready</h2>
            <p style="color:#444;font-size:15px;line-height:1.6;margin:0 0 16px;">
              Thank you for your purchase. Below you'll find the details of your plan and your access link.
            </p>

            <!-- Plan Badge EN -->
            <div style="background:#f0f4ff;border-left:4px solid #1f6fd2;border-radius:6px;padding:14px 18px;margin-bottom:20px;">
              <p style="margin:0 0 4px;font-size:12px;color:#888;text-transform:uppercase;">Your Plan</p>
              <p style="margin:0;font-size:18px;font-weight:700;color:#1f6fd2;">${planNameEn}</p>
            </div>

            <!-- Details EN -->
            <ul style="color:#444;font-size:14px;line-height:2;padding-left:20px;margin:0 0 24px;">
              ${planDetailsEn}
              <li>📧 To recover access anytime, use the "Resend access" option with this email</li>
            </ul>

            <!-- CTA Button EN -->
            <div style="text-align:center;margin:28px 0;">
              <a href="${accessUrl}"
                 style="display:inline-block;background:#27ae60;color:#fff;text-decoration:none;padding:16px 48px;border-radius:10px;font-size:16px;font-weight:700;letter-spacing:0.5px;box-shadow:0 4px 14px rgba(39,174,96,0.4);">
                🚀 Access ZaiOT
              </a>
            </div>

            <!-- Important EN -->
            <div style="background:#fff8e1;border:1px solid #ffd54f;border-radius:6px;padding:14px 18px;margin-bottom:8px;">
              <p style="margin:0;font-size:13px;color:#7d6200;">
                ⚠️ <strong>Important:</strong> Keep this email safe. This link contains your unique access token.
                ${isSingle ? "Your token will be consumed after one successful calculation." : "Each successful calculation consumes one use."}
              </p>
            </div>
          </td>
        </tr>

        <!-- DIVIDER -->
        <tr>
          <td style="padding:0 40px;">
            <hr style="border:none;border-top:2px dashed #e0e0e0;margin:8px 0;" />
          </td>
        </tr>

        <!-- SPANISH SECTION -->
        <tr>
          <td style="padding:24px 40px 36px;">
            <p style="font-size:13px;color:#888;text-transform:uppercase;letter-spacing:1px;margin:0 0 4px;">🇪🇸 Español</p>
            <h2 style="margin:0 0 12px;color:#1a1a2e;font-size:22px;">Tu acceso está listo</h2>
            <p style="color:#444;font-size:15px;line-height:1.6;margin:0 0 16px;">
              Gracias por tu compra. A continuación encontrarás los detalles de tu plan y tu enlace de acceso.
            </p>

            <!-- Plan Badge ES -->
            <div style="background:#f0f4ff;border-left:4px solid #1f6fd2;border-radius:6px;padding:14px 18px;margin-bottom:20px;">
              <p style="margin:0 0 4px;font-size:12px;color:#888;text-transform:uppercase;">Tu Plan</p>
              <p style="margin:0;font-size:18px;font-weight:700;color:#1f6fd2;">${planNameEs}</p>
            </div>

            <!-- Details ES -->
            <ul style="color:#444;font-size:14px;line-height:2;padding-left:20px;margin:0 0 24px;">
              ${planDetailsEs}
              <li>📧 Para recuperar tu acceso en cualquier momento, usa la opción "Reenviar acceso" con este correo</li>
            </ul>

            <!-- CTA Button ES -->
            <div style="text-align:center;margin:28px 0;">
              <a href="${accessUrl}"
                 style="display:inline-block;background:#27ae60;color:#fff;text-decoration:none;padding:16px 48px;border-radius:10px;font-size:16px;font-weight:700;letter-spacing:0.5px;box-shadow:0 4px 14px rgba(39,174,96,0.4);">
                🚀 Acceder a ZaiOT
              </a>
            </div>

            <!-- Important ES -->
            <div style="background:#fff8e1;border:1px solid #ffd54f;border-radius:6px;padding:14px 18px;">
              <p style="margin:0;font-size:13px;color:#7d6200;">
                ⚠️ <strong>Importante:</strong> Guarda este correo. Este enlace contiene tu token de acceso único.
                ${isSingle ? "Tu token se consumirá luego de un cálculo exitoso." : "Cada cálculo exitoso consume un uso."}
              </p>
            </div>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f8f9fc;padding:20px 40px;text-align:center;border-top:1px solid #eee;">
            <p style="margin:0;font-size:12px;color:#aaa;">
              ZaiOT — Overtime Deduction Calculator &nbsp;|&nbsp;
              This is an automated message, please do not reply.
            </p>
            <p style="margin:4px 0 0;font-size:11px;color:#ccc;">
              Este es un mensaje automático, por favor no respondas.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>`;

  // ── Enviar con Resend ──
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: env.EMAIL_FROM,
      to: email,
      subject: isSingle
        ? "ZaiOT — Your access link / Tu enlace de acceso"
        : "ZaiOT — Your subscription access / Tu acceso de suscripción",
      html: html,
    }),
  });
}

// ─────────────────────────────────────────────────────────────
// HELPER — JSON Response con CORS
// ─────────────────────────────────────────────────────────────
function json(data, corsHeaders = {}) {
  return new Response(JSON.stringify(data), {
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders,
    },
  });
}
