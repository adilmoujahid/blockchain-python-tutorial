function registration() {
    let keysBlock = $("#keys-block"),
        privateKey = $("#private_key"),
        publicKey = $("#public_key"),
        result = $('#result-registration');

    $.get('/wallet/new')
        .done(function (data) {
            privateKey.html(data.private_key);
            publicKey.html(data.public_key);
            $("#warning").style.display = "block";
        })
        .fail(function (data) {
            result.html('Вы успешно зарегистрированы!<br>Сохраните ваши ключи и держите их в тайне!').show();
            localStorage.setItem("publicKey", 'hjgugkhj');
            localStorage.setItem("privateKey", 'hjgugkhj');
            keysBlock.show();
            privateKey.html('hjgugkhj');
            publicKey.html("jhgkjhgj");
            $("#warning").style.display = "block";
        })
}

function login() {
    let login = $("#login-public"),
        password = $("#login-private"),
        result = $('#result-login');

    $.get('/wallet/validate')
        .done(function (data) {
            privateKey.html(data.private_key);
            publicKey.html(data.public_key);
            $("#warning").style.display = "block";
        })
        .fail(function (data) {
            //data.success
            if (true) {
                localStorage.setItem("publicKey", login.val());
                localStorage.setItem("privateKey", password.val());
                //Добавить редирект
                result.html("Успешно автроизорованы").addClass("alert-success").removeClass("alert-danger").show();
            } else {
                result.html("Невалидная пара ключей").show();
            }
        })
}