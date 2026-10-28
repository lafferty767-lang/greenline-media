// GREENLINE beta signup: paste into script.google.com, press Run, allow access.
// Creates the Google Form + a Google Sheet that collects the answers.
function makeGreenlineBetaForm() {
  var form = FormApp.create('GREENLINE Beta Signup');
  form.setDescription(
    'GREENLINE is a co-op cube zombie shooter for iPhone and Android by Tufufal Studios. ' +
    'Glo fuel leaked, the town turned into cube zombies, and you and up to 3 friends fight back.\n\n' +
    'Sign up and we will email you a beta invite when testing opens. ' +
    'We only use your email for beta invites and game news, never sold or shared.');
  form.setConfirmationMessage('You are on the list! Watch your email for your beta invite. Follow us for clips and updates: TikTok @playgreenline, Instagram @playgreenline2026.');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);

  form.addTextItem().setTitle('Email').setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());

  form.addMultipleChoiceItem().setTitle('What phone will you play on?').setRequired(true)
    .setChoiceValues(['iPhone', 'Android', 'Both']);

  form.addTextItem().setTitle('Phone model (optional)')
    .setHelpText('Like iPhone 13 or Galaxy S22. Helps us test on lots of phones.');

  form.addCheckboxItem().setTitle('Which of these do you play? (optional)')
    .setChoiceValues(['Call of Duty Zombies', 'Fortnite', 'Brawl Stars', 'Pixel Gun 3D', 'Roblox', 'Minecraft'])
    .showOtherOption(true);

  form.addMultipleChoiceItem().setTitle('Where did you find GREENLINE?')
    .setChoiceValues(['TikTok', 'Instagram', 'YouTube', 'A friend', 'School'])
    .showOtherOption(true);

  form.addCheckboxItem().setTitle('Age check').setRequired(true)
    .setChoiceValues(['I am 13 or older']);

  var sheet = SpreadsheetApp.create('GREENLINE Beta Signups');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('SHARE THIS LINK: ' + form.getPublishedUrl());
  Logger.log('Edit form: ' + form.getEditUrl());
  Logger.log('Answers sheet: ' + sheet.getUrl());
}
