function checkNumber() {
    const guessNumber = parseInt(document.getElementById('guess').value);
    const message = document.getElementById('message');
    const triesDisplay = document.getElementById('tries');

    if (isNaN(guessNumber)) {
        message.innerHTML = "Please enter a valid number.";
        return;
    }

    if (guessNumber === random) {
        message.innerHTML = "You Guessed it Right!";
    } else {
        if (tries > 1) {
            tries--; 
            message.innerHTML = guessNumber > random ? "Make it Lower!" : "Make it Higher!";
        } else {
            message.innerHTML = "Game Over! No more tries left.";
            document.getElementById('guess').disabled = true; 
        }
    }

    triesDisplay.innerHTML = `Tries: ${tries}`;
}
