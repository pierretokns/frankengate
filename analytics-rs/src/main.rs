fn main() {
    if std::env::args().any(|arg| arg == "--check") {
        frankengate_analytics_control::contract_self_check()
            .expect("analytics control-plane contract self-check failed");
        println!(
            "FrankenGate analytics contract v{}: OK",
            frankengate_analytics_control::PROTOCOL_VERSION
        );
    } else if std::env::args().any(|arg| arg == "--serve") {
        serve();
    } else {
        println!("FrankenGate analytics control-plane contract slice");
        println!("Run with --check to validate the leased-job protocol.");
    }
}

fn serve() {
    use std::net::TcpListener;

    // Do not advertise readiness until the control-plane contract itself is
    // executable.  This is intentionally a boot fence: a future durable
    // store must replace this check with its migration/connectivity check.
    frankengate_analytics_control::contract_self_check()
        .expect("analytics control-plane boot fence failed");

    let port = std::env::var("PORT").unwrap_or_else(|_| "8081".into());
    let listener = TcpListener::bind(("0.0.0.0", port.parse::<u16>().expect("PORT must be a u16")))
        .expect("analytics control-plane listener failed to bind");
    println!("FrankenGate analytics control plane listening on 0.0.0.0:{port}");
    for stream in listener.incoming().flatten() {
        std::thread::spawn(|| handle_connection(stream));
    }
}

fn handle_connection(mut stream: std::net::TcpStream) {
    use std::io::{Read, Write};
    let mut request = [0_u8; 1024];
    let size = stream.read(&mut request).unwrap_or(0);
    let path = std::str::from_utf8(&request[..size])
        .ok()
        .and_then(|request| request.split_whitespace().nth(1))
        .unwrap_or("/");
    let (status, content_type, body) = match path {
        "/healthz" | "/readyz" => ("200 OK", "text/plain", "ok\n".to_string()),
        "/version" => (
            "200 OK",
            "text/plain",
            format!(
                "protocol_version={}\n",
                frankengate_analytics_control::PROTOCOL_VERSION
            ),
        ),
        _ => ("404 Not Found", "text/plain", "not found\n".to_string()),
    };
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
}
